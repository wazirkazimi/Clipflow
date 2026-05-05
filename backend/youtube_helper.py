import yt_dlp
import json
import logging
import os

logger = logging.getLogger(__name__)

from yt_dlp.utils import download_range_func

def fetch_youtube_video_info(url: str, download_video=False, output_dir="downloads"):
    """
    Fetches info about a YouTube video, including heatmap data and stream URLs.
    Handles separate video/audio streams for high-quality playback.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            'noplaylist': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['en', 'hi', 'es', 'fr', 'de'],
            'subtitlesformat': 'vtt',
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if download_video:
                # Download the video and subtitles
                ydl.download([url])
                info_dict = ydl.extract_info(url, download=False)  # Get info after download
            else:
                info_dict = ydl.extract_info(url, download=False)
            
            heatmap_data = info_dict.get('heatmap', [])
            
            # Get the actual downloaded file path
            video_id = info_dict.get('id')
            expected_path = os.path.join(output_dir, f"{video_id}.mp4")
            actual_filepath = expected_path if os.path.exists(expected_path) else None
            
            # For high quality, YT uses separate streams. Let's find them.
            video_url = None
            audio_url = None
            
            if 'requested_formats' in info_dict:
                for fmt in info_dict['requested_formats']:
                    if fmt.get('vcodec') != 'none': video_url = fmt.get('url')
                    if fmt.get('acodec') != 'none': audio_url = fmt.get('url')
            else:
                video_url = info_dict.get('url')
                audio_url = video_url # Single file video+audio
            
            if not video_url:
                # Fallback to broad search if requested_formats failed
                formats = info_dict.get('formats', [])
                video_url = info_dict.get('url') or (formats[-1].get('url') if formats else None)
            
            video_info = {
                'id': video_id,
                'title': info_dict.get('title'),
                'duration': info_dict.get('duration'),
                'heatmap': heatmap_data,
                'video_url': video_url,
                'audio_url': audio_url,
                'filepath': actual_filepath or video_url # Use downloaded path if available
            }
            
            print(f"Fetched Info: {video_info['title']} - Duration: {video_info['duration']}s")
            if actual_filepath:
                print(f"Downloaded to: {actual_filepath}")
            
            return video_info
            
    except Exception as e:
        logger.error(f"Error fetching YouTube data: {e}")
        return None
            
    except Exception as e:
        logger.error(f"Error fetching YouTube data: {e}")
        return None
            
    except Exception as e:
        logger.error(f"Error fetching YouTube data: {e}")
        return None

if __name__ == "__main__":
    # Test block
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    res = fetch_youtube_video_info(test_url, download_video=False)
    if res and res.get('heatmap'):
        print("Test extraction successful, heatmap extracted.")
