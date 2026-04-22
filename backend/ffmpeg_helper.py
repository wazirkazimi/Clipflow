import subprocess
import os
import logging
import static_ffmpeg
import datetime
import json
import torch

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

def generate_subtitles(video_path: str, output_ass_path: str, start_time: float = None, duration: float = None, forced_language: str = None):
    """
    Generates an ASS subtitle file with word-level highlighting using OpenAI Whisper.
    Optimized to only transcribe the required segment and reuse the AI model with thread safety.
    """
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
                # Upgrading to 'base' for much better Hindi/Hinglish accuracy
                logger.info(f"Loading Whisper 'base' model into memory ({device})...")
                WHISPER_MODEL_CACHE["model"] = whisper.load_model("base", device=device)
    
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
            # We add a 'prompt' to guide Whisper towards Hinglish (Roman/Hindi/Urdu mixed)
            initial_prompt = "Hindi, Urdu, Hinglish, business, motivation, startup."
            result = model.transcribe(
                temp_audio, 
                word_timestamps=True, 
                fp16=fp16, 
                language=forced_language,
                initial_prompt=initial_prompt
            )
        
        # Print detected text to terminal to help debug
        print(f"\n\033[93m[AI Raw Transcription]:\033[0m {result['text'][:100]}...")

        try:
            from indic_transliteration import sanscript
            from indic_transliteration.sanscript import transliterate
            has_indic = True
        except ImportError:
            has_indic = False

        with open(output_ass_path, "w", encoding="utf-8") as f:
            f.write("[Script Info]\n")
            f.write("ScriptType: v4.00+\n")
            f.write("PlayResX: 1080\n")
            f.write("PlayResY: 1920\n")
            f.write("ScaledBorderAndShadow: yes\n")
            f.write("\n")
            f.write("[V4+ Styles]\n")
            f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
            # Style: Impact font (bold/business style), White text, Yellow/Cyan highlight
            f.write("Style: Default,Impact,100,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,3,2,5,10,10,100,1\n")
            f.write("\n")
            f.write("[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

            # Collect all words from all segments
            all_words = []
            for segment in result['segments']:
                all_words.extend(segment.get('words', []))

            # Group words into chunks of 3
            chunk_size = 3
            for i in range(0, len(all_words), chunk_size):
                chunk = all_words[i : i + chunk_size]
                if not chunk:
                    continue

                # For each word in the chunk, create a dialogue event
                for highlight_idx, current_word in enumerate(chunk):
                    start_ts = format_timestamp(current_word['start'])
                    end_ts = format_timestamp(current_word['end'])
                    
                    # Build the chunk phrase with the current word highlighted
                    phrase = ""
                    for word_idx, wd in enumerate(chunk):
                        text = wd['word'].strip()
                        
                        # Convert to Hinglish if Hindi or Urdu script is detected
                        if has_indic:
                            if is_hindi_script(text):
                                text = transliterate(text, sanscript.DEVANAGARI, sanscript.ISO)
                            elif is_urdu_script(text):
                                # Using URDU scheme to Romanization
                                text = transliterate(text, sanscript.URDU, sanscript.ISO)
                        
                        text = text.upper()
                        
                        if word_idx == highlight_idx:
                            # Highlight current word in Yellow (&H0000FFFF) or Cyan (&H00FFFF)
                            phrase += f"{{\\c&H00FFFF&}}{text}{{\\c&HFFFFFF&}} "
                        else:
                            phrase += f"{text} "
                    
                    f.write(f"Dialogue: 0,{start_ts},{end_ts},Default,,0,0,0,,{phrase.strip()}\n")
    
    except Exception as e:
        logger.error(f"Error during subtitle generation: {e}")
        return False
    finally:
        # Clean up the temporary audio file
        if os.path.exists(temp_audio):
            try: os.remove(temp_audio)
            except: pass

    return True

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
        inputs = [
            "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
            "-ss", str(start_time), "-t", str(duration), "-i", main_video_path
        ]
        
        if main_audio_path and main_audio_path != main_video_path:
            inputs += [
                "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
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
            if generate_subtitles(source_for_audio, ass_path, start_time, duration, forced_language=forced_language):
                escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
                command[command.index("-filter_complex") + 1] += f";[v]subtitles='{escaped_ass_path}'[v]"
            else:
                logger.warning("Captions requested but failed to generate.")

        # Add logo overlay if exists
        if logo_input_index is not None:
            command[command.index("-filter_complex") + 1] += f";[v][{logo_input_index}:v]overlay=W-w-30:30[v]"

        command += ["-map", "[v]"]

        command += [
            "-map", audio_stream_index,
            "-t", str(duration),
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]
        
        logger.info(f"Running FFmpeg: {' '.join(command)}")
        
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
            if generate_subtitles(reel_video_path, ass_path, 0, reel_duration, forced_language=forced_language):
                escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
                command[command.index("-filter_complex") + 1] += f";[v]subtitles='{escaped_ass_path}'[v]"
                # The mapping will be added below
            else:
                logger.warning("Captions requested but failed to generate.")

        command += ["-map", "[v]"]

        command += [
            "-map", "0:a",  # Use audio from reel video
            "-t", str(reel_duration),  # Match the reel duration
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
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
        inputs = [
            "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
            "-ss", str(start_time), "-t", str(duration), "-i", main_video_path
        ]
        
        if main_audio_path and main_audio_path != main_video_path:
            inputs += [
                "-reconnect", "1", "-reconnect_at_eof", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "2",
                "-ss", str(start_time), "-t", str(duration), "-i", main_audio_path
            ]
            audio_stream_index = "1:a"
            
        command = [
            "ffmpeg", "-y"
        ] + inputs + [
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}",
            "-map", "0:v",
        ]

        if add_captions:
            ass_path = output_path.replace(".mp4", ".ass")
            source_for_audio = main_video_path if not main_audio_path else main_audio_path
            if generate_subtitles(source_for_audio, ass_path, start_time, duration, forced_language=forced_language):
                escaped_ass_path = ass_path.replace("\\", "/").replace(":", "\\:")
                # For vertical crop, we used -vf. Let's switch to -filter_complex for consistency if we add logo
                vf_val = command[command.index("-vf") + 1]
                command.pop(command.index("-vf") + 1)
                command[command.index("-vf")] = "-filter_complex"
                command.insert(command.index("-filter_complex") + 1, f"[0:v]{vf_val}[v];[v]subtitles='{escaped_ass_path}'[v]")
            else:
                # Convert -vf to [v] mapping anyway
                vf_val = command[command.index("-vf") + 1]
                command.pop(command.index("-vf") + 1)
                command[command.index("-vf")] = "-filter_complex"
                command.insert(command.index("-filter_complex") + 1, f"[0:v]{vf_val}[v]")
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
            "-preset", "veryfast",
            "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_path
        ]
        
        logger.info(f"Creating vertical crop video: {' '.join(command)}")
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
