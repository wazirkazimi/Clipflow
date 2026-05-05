import subprocess
import os
import logging
import static_ffmpeg
import datetime
import json
import re
import shutil

try:
    import torch
except ImportError:
    torch = None

static_ffmpeg.add_paths() # Ensures ffmpeg/ffprobe are in the PATH

logger = logging.getLogger(__name__)

def format_timestamp(seconds: float):
    """Formats seconds into ASS subtitle timestamp format (H:MM:SS.CC)"""
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 10000)
    return f"{hours:01d}:{minutes:02d}:{secs:02d}.{millis:02d}"

def is_hindi_script(text: str) -> bool:
    """Checks if a string contains Devanagari (Hindi) characters."""
    return any('\u0900' <= c <= '\u097f' for c in text)

def is_urdu_script(text: str) -> bool:
    """Checks if a string contains Urdu/Arabic characters."""
    return any('\u0600' <= c <= '\u06ff' for c in text)

import threading

WHISPER_MODEL_CACHE = {}
WHISPER_LOCK = threading.Lock()

def extract_embedded_subtitles(video_path: str, output_ass_path: str):
    """Extract embedded subtitles from video file using ffmpeg."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "s",
            "-show_entries", "stream=index", "-of", "csv=p=0",
            video_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.stdout.strip():
            logger.info(f"Found embedded subtitle streams: {result.stdout.strip()}")
            cmd_extract = [
                "ffmpeg", "-y", "-i", video_path, "-map", "0:s:0",
                output_ass_path
            ]
            result = subprocess.run(cmd_extract, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0 and os.path.exists(output_ass_path):
                logger.info(f"Successfully extracted embedded subtitles to {output_ass_path}")
                return True
    except Exception as e:
        logger.warning(f"Could not extract embedded subtitles: {e}")
    return False

def transliterate_word(token: str) -> str:
    """Transliterate Hindi/Urdu tokens into Roman script for Hinglish captions."""
    try:
        from indic_transliteration import sanscript
        from indic_transliteration.sanscript import transliterate
    except ImportError:
        return token

    if is_hindi_script(token):
        rom = transliterate(token, sanscript.DEVANAGARI, sanscript.ITRANS).lower()
        return rom[:-1] if rom.endswith('a') and len(rom) > 3 else rom
    if is_urdu_script(token):
        rom = transliterate(token, sanscript.URDU, sanscript.ITRANS).lower()
        return rom[:-1] if rom.endswith('a') and len(rom) > 3 else rom
    return token


def generate_subtitles(video_path: str, output_ass_path: str, start_time: float = None, duration: float = None, forced_language: str = None, width: int = 1080, height: int = 1920):
    """
    Generates an ASS subtitle file with TikTok/Reels-style burned-in captions.
    It first tries to extract embedded subtitles from the source video, then falls back to Whisper transcription.
    Captions use bold styling, animated emphasis, keyword highlighting, and are burned directly into the clip.
    """
    # Step 1: Try to extract embedded subtitles first
    temp_extracted = output_ass_path.replace(".ass", "_extracted.ass")
    if extract_embedded_subtitles(video_path, temp_extracted):
        logger.info("Using extracted embedded subtitles")
        try:
            shutil.copy(temp_extracted, output_ass_path)
            if os.path.exists(temp_extracted):
                os.remove(temp_extracted)
            return True
        except Exception as e:
            logger.warning(f"Failed to use extracted subtitles: {e}")
            if os.path.exists(temp_extracted):
                try: os.remove(temp_extracted)
                except: pass
    
    # Step 2: Fall back to Whisper transcription if no embedded subtitles
    if torch is None:
        logger.error("OpenAI Whisper/torch not installed. Run 'pip install openai-whisper torch'")
        return False
    
    try:
        import whisper
    except ImportError:
        logger.error("OpenAI Whisper not installed. Run 'pip install openai-whisper torch'")
        return False

    global WHISPER_MODEL_CACHE, WHISPER_LOCK
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    if "model" not in WHISPER_MODEL_CACHE:
        # We lock the loading part too just in case
        with WHISPER_LOCK:
            if "model" not in WHISPER_MODEL_CACHE:
                # Using 'small' model for much better Hindi/Hinglish accuracy (95%+)
                logger.info(f"Loading Whisper 'small' model into memory ({device})...")
                WHISPER_MODEL_CACHE["model"] = whisper.load_model("small", device=device)
    
    model = WHISPER_MODEL_CACHE["model"]
    temp_audio = output_ass_path.replace(".ass", "_temp.wav")
    
    try:
        # Step 1: Extract ONLY the audio segment needed for the clip
        # This makes it 100x faster for long videos
        extract_cmd = [
            "ffmpeg", "-y", "-ss", str(start_time or 0), "-t", str(duration or 30),
            "-i", video_path, "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1", temp_audio
        ]
        subprocess.run(extract_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

        logger.info(f"Transcribing audio segment for captions...")
        fp16 = torch.cuda.is_available()
        
        # Use a lock so multiple threads don't call the AI at once
        with WHISPER_LOCK:
            initial_prompt = (
                "Transcribe the spoken audio. For Hindi parts, use Hindi script (Devanagari). "
                "For English words, write them in English. Example: 'ये ONE mistake तुम्हारी growth रोक रही है'."
            )
            language_code = None
            if forced_language:
                if forced_language.lower().startswith("h"):
                    language_code = "hi"
                elif forced_language.lower().startswith("u"):
                    language_code = "ur"
                else:
                    language_code = forced_language.lower()

            transcribe_args = {
                "word_timestamps": True,
                "fp16": fp16,
                "initial_prompt": initial_prompt
            }
            if language_code is not None:
                transcribe_args["language"] = language_code

            result = model.transcribe(temp_audio, **transcribe_args)
        
        # Print detected text to terminal to help debug
        print(f"\n\033[93m[AI Raw Transcription]:\033[0m {result.get('text', '')[:120]}...")

        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            has_indic = True
        except ImportError:
            has_indic = False

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write("[Script Info]\n")
            f.write("ScriptType: v4.00+\n")
            f.write(f"PlayResX: {width}\n")
            f.write(f"PlayResY: {height}\n")
            f.write("ScaledBorderAndShadow: yes\n")
            f.write("\n")
            f.write("[V4+ Styles]\n")
            f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            f.write("Style: CaptionBody,Arial Black,96,&H00FFFFFF,&H00000000,&H00000000,&HFF000000,-1,0,0,0,120,120,0,0,1,15,8,20,20,80,1\n")
            f.write("Style: AnimCaption,Arial Black,96,&H00FFFFFF,&H00000000,&H00000000,&HFF000000,-1,0,0,0,120,120,0,0,1,15,8,20,20,80,1\n")
            f.write("Style: Highlight,Arial Black,96,&H00FFFF00,&H00000000,&H00000000,&HFF000000,-1,0,0,0,120,120,0,0,1,15,8,20,20,80,1\n")
            f.write("\n")
            f.write("[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

            # Collect all words from all segments
            all_words = []
            for segment in result.get('segments', []):
                all_words.extend(segment.get('words', []))

            def format_chunk_word(token: str) -> str:
                token = token.strip()
                # If the token contains Devanagari, it transliterates to lowercase Roman Hindi.
                # If it's purely English characters, it becomes UPPERCASE for emphasis.
                if is_hindi_script(token) or is_urdu_script(token):
                    if has_indic:
                        token = transliterate_word(token)
                else:
                    token = token.upper()
                return token.replace('{', '\\{').replace('}', '\\}')

            viral_keywords = {
                'BEST', 'ONE', 'DOUBLE', 'VIEWS', 'VIRAL', 'TRICK', 'FREE', 'NOW', 'MUST',
                'EASY', 'TOP', 'AMAZING', 'CRAZY', 'SECRET', 'HACK', 'WIN', 'GROW', 'MONEY',
                'STORY', 'POWER', 'NEVER', 'ACTUALLY', 'TODAY', 'LEARN', 'WHY', 'WATCH'
            }

            def pick_highlight_word(words: list) -> str:
                for word in words:
                    normalized = re.sub(r"[^\\w]", "", word)
                    if normalized in viral_keywords:
                        return word
                longer_words = [w for w in words if len(re.sub(r"[^\\w]", "", w)) >= 4]
                return longer_words[0] if longer_words else words[0]

            wrote_dialogues = False
            last_end = 0.0

            def write_chunk_animated(chunk_words_with_times: list):
                nonlocal wrote_dialogues, last_end
                if not chunk_words_with_times:
                    return

                # extract just the text
                phrase_words = [wd['word'] for wd in chunk_words_with_times]
                
                # Capitalize the first letter of the chunk if it's lowercase (Roman Hindi)
                if phrase_words and phrase_words[0].islower():
                    phrase_words[0] = phrase_words[0].capitalize()
                
                for w_idx, wd in enumerate(chunk_words_with_times):
                    start = wd['start']
                    end = wd['end']
                    if start < last_end:
                        start = last_end
                    
                    if end - start < 0.1:
                        end = start + 0.1
                        
                    rendered_phrase = []
                    for pw_idx, pw in enumerate(phrase_words):
                        is_current = (pw_idx == w_idx)
                        
                        # Current spoken word gets the yellow highlight color
                        color = "&H0000FFFF" if is_current else "&H00FFFFFF"
                        
                        if is_current:
                            rendered_phrase.append(
                                f"{{\\c{color}\\fs115\\t(0,100,\\fs125)\\t(100,200,\\fs115)}}" + pw + f"{{\\c&H00FFFFFF\\fs96}}"
                            )
                        else:
                            rendered_phrase.append(
                                f"{{\\c{color}\\fs96}}" + pw + f"{{\\c&H00FFFFFF\\fs96}}"
                            )
                            
                    full_phrase_ass = " ".join(rendered_phrase)
                    
                    # Position center-middle: \an5 means exact center alignment.
                    # Placing it at height//2 puts it right on the border of split screen.
                    center_x = width // 2
                    pos_y = height // 2
                    subtitle_text = (
                        f"{{\\an5\\pos({center_x},{pos_y})\\bord8\\shad4}}"
                        f"{full_phrase_ass}"
                    )
                    
                    f.write(
                        f"Dialogue: 0,{format_timestamp(start)},{format_timestamp(end)},"
                        f"AnimCaption,,0,0,0,,{subtitle_text}\n"
                    )
                    
                    last_end = end
                    wrote_dialogues = True

            if all_words:
                chunk_size = 3  # 2-3 words per line
                for i in range(0, len(all_words), chunk_size):
                    chunk = all_words[i : i + chunk_size]
                    if not chunk:
                        continue
                    
                    formatted_chunk = []
                    for wd in chunk:
                        formatted_chunk.append({
                            'word': format_chunk_word(wd['word']),
                            'start': wd['start'],
                            'end': wd['end']
                        })
                        
                    write_chunk_animated(formatted_chunk)
            else:
                # Fallback: use segment-level text if Whisper did not return word timestamps
                for segment in result.get('segments', []):
                    segment_text = segment.get('text', '').strip()
                    if not segment_text:
                        continue
                    words = [format_chunk_word(w) for w in segment_text.split() if w.strip()]
                    if not words:
                        continue
                    start = max(segment['start'] - 0.05, 0.0)
                    end = segment['end'] + 0.08
                    chunk_size = 3
                    total_chunks = (len(words) + chunk_size - 1) // chunk_size
                    segment_duration = max(end - start, 0.1)
                    chunk_duration = segment_duration / max(total_chunks, 1)
                    for idx in range(total_chunks):
                        chunk_words = words[idx * chunk_size : (idx + 1) * chunk_size]
                        if not chunk_words:
                            continue
                        chunk_start = start + idx * chunk_duration
                        chunk_end = min(end, chunk_start + len(chunk_words) * chunk_duration)
                        word_dur = (chunk_end - chunk_start) / len(chunk_words)
                        formatted_chunk = []
                        for i_w, cw in enumerate(chunk_words):
                            formatted_chunk.append({
                                'word': cw,
                                'start': chunk_start + i_w * word_dur,
                                'end': chunk_start + (i_w + 1) * word_dur
                            })
                        write_chunk_animated(formatted_chunk)

            if not wrote_dialogues:
                full_text = result.get('text', '').strip()
                if full_text:
                    words = [format_chunk_word(w) for w in full_text.split() if w.strip()]
                    if words:
                        chunk_size = 3
                        total_chunks = (len(words) + chunk_size - 1) // chunk_size
                        clip_duration = float(duration or 5.0)
                        chunk_duration = max(clip_duration / max(total_chunks, 1), 0.5)
                        for idx in range(total_chunks):
                            chunk_words = words[idx * chunk_size : (idx + 1) * chunk_size]
                            if not chunk_words:
                                continue
                            chunk_start = min(idx * chunk_duration, clip_duration - 0.1)
                            chunk_end = min(clip_duration, chunk_start + chunk_duration)
                            word_dur = (chunk_end - chunk_start) / len(chunk_words)
                            formatted_chunk = []
                            for i_w, cw in enumerate(chunk_words):
                                formatted_chunk.append({
                                    'word': cw,
                                    'start': chunk_start + i_w * word_dur,
                                    'end': chunk_start + (i_w + 1) * word_dur
                                })
                            write_chunk_animated(formatted_chunk)
    except Exception as e:
        logger.error(f"Error during subtitle generation: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Clean up the temporary audio file
        if os.path.exists(temp_audio):
            try: os.remove(temp_audio)
            except: pass

    if os.path.exists(output_ass_path):
        logger.info(f"✓ ASS subtitle file created successfully: {output_ass_path}")
        print(f"\033[92m[✓ SUBTITLES]\033[0m Generated: {output_ass_path}\n")
    return True


def find_local_vtt_paths(video_path: str):
    """Find local VTT subtitle files for a downloaded video."""
    video_id = os.path.splitext(os.path.basename(video_path))[0]
    video_dir = os.path.dirname(video_path) or '.'
    found = []
    if os.path.isdir(video_dir):
        for file_name in os.listdir(video_dir):
            if file_name.startswith(video_id + '.') and file_name.endswith('.vtt'):
                found.append(os.path.join(video_dir, file_name))
    return found


def generate_ass_from_vtt(vtt_path: str, ass_path: str, start_time: float = 0.0, duration: float = 30.0, width: int = 1080, height: int = 1920):
    """Convert a VTT transcript into an ASS subtitle file for vertical shorts."""
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        cues = []
        current_times = None
        current_text = []

        for line in lines:
            stripped = line.strip()
            if '-->' in stripped:
                parts = stripped.split('-->')
                if len(parts) == 2:
                    def parse_time(ts: str):
                        ts = ts.strip().split(' ')[0]
                        h, m, s = ts.replace(',', '.').split(':')
                        return float(h) * 3600 + float(m) * 60 + float(s)
                    start = parse_time(parts[0])
                    end = parse_time(parts[1])
                    current_times = (start, end)
                    current_text = []
            elif stripped == '' and current_times and current_text:
                text = ' '.join(current_text).strip()
                if text:
                    cues.append((current_times[0], current_times[1], text))
                current_times = None
                current_text = []
            elif current_times:
                text_line = stripped
                if text_line and not text_line.startswith('WEBVTT'):
                    text_line = re.sub(r'<[^>]+>', '', text_line)
                    current_text.append(text_line)

        if current_times and current_text:
            text = ' '.join(current_text).strip()
            if text:
                cues.append((current_times[0], current_times[1], text))

        with open(ass_path, 'w', encoding='utf-8') as f:
            f.write('[Script Info]\n')
            f.write('ScriptType: v4.00+\n')
            f.write(f'PlayResX: {width}\n')
            f.write(f'PlayResY: {height}\n')
            f.write('ScaledBorderAndShadow: yes\n\n')
            f.write('[V4+ Styles]\n')
            f.write('Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, '
                    'Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, '
                    'Alignment, MarginL, MarginR, MarginV, Encoding\n')
            f.write('Style: CaptionBody,Arial Black,88,&H00FFFFFF,&H00000000,&H00000000,&HFF000000,-1,0,0,0,120,120,0,0,1,6,0,4,20,20,60,1\n')
            f.write('Style: AnimCaption,Arial Black,88,&H00FFFFFF,&H00000000,&H00000000,&HFF000000,-1,0,0,0,120,120,0,0,1,6,0,4,20,20,60,1\n\n')
            f.write('[Events]\n')
            f.write('Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n')

            viral_keywords = {
                'best', 'one', 'double', 'views', 'viral', 'trick', 'free', 'now', 'must',
                'easy', 'top', 'amazing', 'crazy', 'secret', 'hack', 'win', 'grow', 'money',
                'story', 'power', 'never', 'actually', 'today', 'learn', 'why', 'watch'
            }

            def highlight_ass_text(phrase: str) -> str:
                words = phrase.split()
                if not words:
                    return phrase
                for word in words:
                    normalized = re.sub(r"[^\\w]", "", word.lower())
                    if normalized in viral_keywords:
                        highlight = word
                        break
                else:
                    content_words = [w for w in words if len(re.sub(r"[^\\w]", "", w)) >= 4]
                    highlight = content_words[0] if content_words else words[0]
                rendered = []
                for token in words:
                    if token == highlight:
                        rendered.append(f"{{\\b1\\fs110\\c&H00FFFF00}}{token}{{\\b0\\fs100\\c&H00FFFFFF}}")
                    else:
                        rendered.append(token)
                return " ".join(rendered)

            end_time = start_time + duration
            for cue_start, cue_end, cue_text in cues:
                if cue_end <= start_time or cue_start >= end_time:
                    continue
                relative_start = max(cue_start, start_time) - start_time
                relative_end = min(cue_end, end_time) - start_time
                if relative_end <= 0 or relative_start >= duration:
                    continue
                def to_ass(ts: float):
                    hours = int(ts // 3600)
                    mins = int((ts % 3600) // 60)
                    secs = ts % 60
                    return f'{hours}:{mins:02d}:{secs:05.2f}'
                text = re.sub(r'\s+', ' ', cue_text).strip()
                if not text:
                    continue
                words = []
                for w in text.split():
                    w = w.strip()
                    if is_hindi_script(w) or is_urdu_script(w):
                        w = transliterate_word(w)
                    else:
                        w = w.upper()
                    words.append(w.replace('{', '\\{').replace('}', '\\}'))
                    
                center_x = width // 2
                pos_y = height // 2
                if len(words) <= 3:
                    if words and words[0].islower():
                        words[0] = words[0].capitalize()
                    chunk_text = " ".join(words)
                    duration_ms = int((relative_end - relative_start) * 1000)
                    f.write(
                        f'Dialogue: 0,{to_ass(relative_start)},{to_ass(relative_end)},AnimCaption,,0,0,0,,'
                        f'{{\\an5\\pos({center_x},{pos_y})\\bord6\\shad0\\fs100\\t(0,150,\\fs88)}}{highlight_ass_text(chunk_text)}\\n'
                    )
                else:
                    num_chunks = (len(words) + 2) // 3
                    chunk_duration = (relative_end - relative_start) / num_chunks
                    for chunk_index in range(num_chunks):
                        chunk_words = words[chunk_index*3:(chunk_index+1)*3]
                        if chunk_words and chunk_words[0].islower():
                            chunk_words[0] = chunk_words[0].capitalize()
                        chunk_start = relative_start + chunk_index * chunk_duration
                        chunk_end = min(relative_end, chunk_start + chunk_duration)
                        chunk_text = " ".join(chunk_words).replace('{', '\\{').replace('}', '\\}')
                        f.write(
                            f'Dialogue: 0,{to_ass(chunk_start)},{to_ass(chunk_end)},AnimCaption,,0,0,0,,'
                            f'{{\\an5\\pos({center_x},{pos_y})\\bord6\\shad0\\fs100\\t(0,150,\\fs88)}}{highlight_ass_text(chunk_text)}\n'
                        )

        return True
    except Exception as e:
        logger.error(f'Error converting VTT to ASS: {e}')
        return False


def create_split_screen_short(
    main_video_path: str, 
    gameplay_video_path: str, 
    output_path: str, 
    start_time: float, 
    duration: float = 30.0,
    main_audio_path: str = None,
    width: int = 1080,
    height: int = 1920,
    add_captions: bool = True,
    forced_language: str = None
):
    """
    Creates a 9:16 YouTube Short by taking a segment from the main video,
    looping a gameplay video, extracting the desired length, and combining them
    in a vertical split screen (top/bottom).
    """
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        half_height = height // 2
        
        # FFmpeg command to achieve the split screen:
        # -ss sets start time, -t sets duration for the main video.
        # -stream_loop -1 on gameplay video ensures it plays long enough for the duration.
        # Filters: scale and crop both videos to 1080x960. Then vstack merges them.
        # If separate audio path is given:
        # Input 0: Main Video
        # Input 1: Gameplay Video (if no separate audio)
        # Input 1: Main Audio (if separate audio provided)
        # Input 2: Gameplay Video (if separate audio provided)
        
        audio_stream_index = "0:a"
        gameplay_input_index = "1:v"
        is_url = main_video_path.startswith(('http://', 'https://'))
        inputs = []
        if is_url:
            inputs += [
                "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
            ]
        inputs += [
            "-ss", str(start_time), "-t", str(duration), "-i", main_video_path
        ]
        
        if main_audio_path and main_audio_path != main_video_path:
            if is_url or main_audio_path.startswith(('http://', 'https://')):
                inputs += [
                    "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
                ]
            inputs += [
                "-ss", str(start_time), "-t", str(duration), "-i", main_audio_path
            ]
            audio_stream_index = "1:a" 
            gameplay_input_index = "2:v"
            
        command = [
            "ffmpeg", "-y"
        ] + inputs + [
            "-stream_loop", "-1", "-i", gameplay_video_path,
            "-filter_complex",
            f"[0:v]scale={width}:{half_height}:force_original_aspect_ratio=increase,crop={width}:{half_height}[top];"
            f"[{gameplay_input_index}]scale={width}:{half_height}:force_original_aspect_ratio=increase,crop={width}:{half_height}[bottom];"
            f"[top][bottom]vstack=inputs=2[v]",
        ]
        
        # Logo logic disabled by user request for now
        logo_path = None # "assets/logo.png"
        logo_input_index = None
        
        # Add subtitles filter if requested
        if add_captions:
            ass_path = output_path.replace(".mp4", ".ass")
            source_for_audio = main_video_path if not main_audio_path else main_audio_path
            caption_ready = False

            if generate_subtitles(source_for_audio, ass_path, start_time, duration, forced_language=forced_language, width=width, height=height):
                caption_ready = True
            else:
                logger.warning("Whisper subtitle generation failed, trying local VTT fallback.")
                vtt_files = find_local_vtt_paths(main_video_path)
                if vtt_files:
                    for vtt_path in vtt_files:
                        if generate_ass_from_vtt(vtt_path, ass_path, start_time, duration, width=width, height=height):
                            caption_ready = True
                            break

            if caption_ready:
                escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
                logger.info(f"✓ Subtitles ready: {ass_path}")
                logger.info(f"✓ Adding subtitles filter with ASS: {escaped_ass_path}")
                command[command.index("-filter_complex") + 1] += f";[v]subtitles='{escaped_ass_path}':force_style='Fontname=Arial Black,Fontsize=96,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=6,Shadow=0,BackColour=&H00000000'[v]"
                print(f"\n\033[92m[SUBTITLES ENABLED]\033[0m ASS file: {ass_path}\n")
            else:
                logger.warning("Captions requested but failed to generate.")
                print(f"\n\033[91m[WARNING] Could not generate subtitles for: {source_for_audio}\033[0m\n")

        # Add logo overlay if exists
        if logo_input_index is not None:
            command[command.index("-filter_complex") + 1] += f";[v][{logo_input_index}:v]overlay=W-w-30:30[v]"

        command += ["-map", "[v]"]

        command += [
            "-map", audio_stream_index,
            "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "superfast",
            "-crf", "24",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]
        
        logger.info(f"Running FFmpeg for split screen with captions...")
        logger.debug(f"FFmpeg command: {' '.join(command)}")
        print(f"\033[94m[Running FFmpeg]\033[0m Processing clip with {('captions' if add_captions else 'no captions')}...\n")
        
        # Execute the command
        result = subprocess.run(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False, result.stderr
            
        # Clean up the subtitle file after successful burn-in
        if add_captions:
            ass_path = output_path.replace(".mp4", ".ass")
            if os.path.exists(ass_path):
                try: os.remove(ass_path)
                except: pass

        return True, output_path
        
    except Exception as e:
        logger.error(f"Error in split screen creation: {e}")
        return False, str(e)

def get_video_duration(video_path: str):
    """
    Gets the duration of a video file in seconds using ffprobe.
    """
    try:
        command = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1:noprint_wrappers=1", video_path
        ]
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        logger.error(f"Error getting video duration: {e}")
        return None

def create_reel_composite_video(
    reel_video_path: str,
    gameplay_video_path: str,
    output_path: str,
    width: int = 1080,
    height: int = 1920,
    add_captions: bool = True,
    forced_language: str = None
):
    """
    Creates a composite MP4 video with the Instagram reel video at the top
    and a gameplay video at the bottom, matching the reel's duration.
    
    Args:
        reel_video_path: Path to the Instagram reel video
        gameplay_video_path: Path to the gameplay video
        output_path: Path to save the composite video (should be .mp4)
        width: Width of the final video (default: 1080)
        height: Height of the final video (default: 1920)
    
    Returns:
        (success: bool, message: str)
    """
    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # Get the duration of the reel video
        reel_duration = get_video_duration(reel_video_path)
        if reel_duration is None:
            return False, "Could not determine reel video duration"
        
        logger.info(f"Reel duration: {reel_duration} seconds")
        
        half_height = height // 2
        
        # Create composite video with reel on top and looping gameplay on bottom
        # The gameplay video will be looped to match the reel duration
        command = [
            "ffmpeg", "-y",
            "-i", reel_video_path,
            "-stream_loop", "-1", "-i", gameplay_video_path,
            "-filter_complex",
            f"[0:v]scale={width}:{half_height}:force_original_aspect_ratio=increase,crop={width}:{half_height}[top];"
            f"[1:v]scale={width}:{half_height}:force_original_aspect_ratio=increase,crop={width}:{half_height}[bottom];"
            f"[top][bottom]vstack=inputs=2[v]",
        ]

        if add_captions:
            ass_path = output_path.replace(".mp4", ".ass")
            # For reels, we use the start of the file (0) and the reel's duration
            if generate_subtitles(reel_video_path, ass_path, 0, reel_duration, forced_language=forced_language, width=width, height=height):
                escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
                command[command.index("-filter_complex") + 1] += f";[v]subtitles='{escaped_ass_path}':force_style='Fontname=Arial Black,Fontsize=96,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=6,Shadow=0,BackColour=&H00000000'[v]"
                # The mapping will be added below
            else:
                logger.warning("Captions requested but failed to generate.")

        command += ["-map", "[v]"]

        command += [
            "-map", "0:a",  # Use audio from reel video
            "-t", str(reel_duration),  # Match the reel duration
            "-c:v", "libx264",
            "-preset", "superfast",
            "-crf", "24",
            "-c:a", "aac",
            output_path
        ]
        
        logger.info(f"Creating composite video: {' '.join(command)}")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False, result.stderr
        
        # Clean up the subtitle file after successful burn-in
        if add_captions:
            ass_path = output_path.replace(".mp4", ".ass")
            if os.path.exists(ass_path):
                try: os.remove(ass_path)
                except: pass

        return True, output_path
        
    except Exception as e:
        logger.error(f"Error in reel composite video creation: {e}")
        return False, str(e)

def create_vertical_crop_short(
    main_video_path: str,
    output_path: str,
    start_time: float,
    duration: float = 30.0,
    main_audio_path: str = None,
    width: int = 1080,
    height: int = 1920,
    add_captions: bool = True,
    forced_language: str = None
):
    """
    Creates a 9:16 vertical short by cropping the main video.
    """
    try:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        audio_stream_index = "0:a"
        is_url = main_video_path.startswith(('http://', 'https://'))
        inputs = []
        if is_url:
            inputs += [
                "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
            ]
        inputs += [
            "-ss", str(start_time), "-t", str(duration), "-i", main_video_path
        ]
        
        if main_audio_path and main_audio_path != main_video_path:
            if is_url or main_audio_path.startswith(('http://', 'https://')):
                inputs += [
                    "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
                ]
            inputs += [
                "-ss", str(start_time), "-t", str(duration), "-i", main_audio_path
            ]
            audio_stream_index = "1:a"
            
        command = [
            "ffmpeg", "-y"
        ] + inputs + [
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
        ]

        if add_captions:
            ass_path = output_path.replace(".mp4", ".ass")
            source_for_audio = main_video_path if not main_audio_path else main_audio_path
            caption_ready = False
            if generate_subtitles(source_for_audio, ass_path, start_time, duration, forced_language=forced_language, width=width, height=height):
                caption_ready = True
            else:
                logger.warning("Whisper subtitle generation failed, trying local VTT fallback.")
                vtt_files = find_local_vtt_paths(main_video_path)
                if vtt_files:
                    for vtt_path in vtt_files:
                        if generate_ass_from_vtt(vtt_path, ass_path, start_time, duration, width=width, height=height):
                            caption_ready = True
                            break

            vf_val = command[command.index("-vf") + 1]
            command.pop(command.index("-vf") + 1)
            command[command.index("-vf")] = "-filter_complex"
            if caption_ready:
                escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
                logger.info(f"✓ Subtitles ready: {ass_path}")
                logger.info(f"✓ Adding subtitles filter with ASS: {escaped_ass_path}")
                command.insert(command.index("-filter_complex") + 1, f"[0:v]{vf_val}[v];[v]subtitles='{escaped_ass_path}':force_style='Fontname=Arial Black,Fontsize=96,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=6,Shadow=0,BackColour=&H00000000'[v]")
                print(f"\n\033[92m[SUBTITLES ENABLED]\033[0m ASS file: {ass_path}\n")
            else:
                command.insert(command.index("-filter_complex") + 1, f"[0:v]{vf_val}[v]")
                print(f"\n\033[91m[WARNING] Could not generate subtitles\033[0m\n")
        else:
            vf_val = command[command.index("-vf") + 1]
            command.pop(command.index("-vf") + 1)
            command[command.index("-vf")] = "-filter_complex"
            command.insert(command.index("-filter_complex") + 1, f"[0:v]{vf_val}[v]")

        # Check for logo - Disabled by user request
        logo_path = None # "assets/logo.png"
        if logo_path and os.path.exists(logo_path):
            command.insert(command.index("-filter_complex"), "-i")
            command.insert(command.index("-filter_complex"), logo_path)
            logo_input_index = command.count("-i") - 1
            command[command.index("-filter_complex") + 1] += f";[v][{logo_input_index}:v]overlay=W-w-30:30[v]"
        
        command += [
            "-map", "[v]",
            "-map", audio_stream_index,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "superfast",
            "-crf", "24",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]
        
        logger.info(f"Running FFmpeg for vertical crop...")
        logger.debug(f"FFmpeg command: {' '.join(command)}")
        print(f"\033[94m[Running FFmpeg]\033[0m Processing vertical clip with {('captions' if add_captions else 'no captions')}...\n")
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            return False, result.stderr
            
        # Clean up the subtitle file after successful burn-in
        if add_captions:
            ass_path = output_path.replace(".mp4", ".ass")
            if os.path.exists(ass_path):
                try: os.remove(ass_path)
                except: pass

        return True, output_path
        
    except Exception as e:
        logger.error(f"Error in vertical crop creation: {e}")
        return False, str(e)

if __name__ == "__main__":
    pass
