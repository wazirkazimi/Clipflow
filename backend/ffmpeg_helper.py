import subprocess
import os
import logging
import static_ffmpeg

static_ffmpeg.add_paths() # Ensures ffmpeg/ffprobe are in the PATH

logger = logging.getLogger(__name__)

def create_split_screen_short(
    main_video_path: str, 
    gameplay_video_path: str, 
    output_path: str, 
    start_time: float, 
    duration: float = 30.0,
    main_audio_path: str = None,
    width: int = 1080,
    height: int = 1920
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
            "-map", "[v]",
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
    height: int = 1920
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
            "-map", "[v]",
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
    height: int = 1920
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
            
        return True, output_path
        
    except Exception as e:
        logger.error(f"Error in vertical crop creation: {e}")
        return False, str(e)

if __name__ == "__main__":
    pass
