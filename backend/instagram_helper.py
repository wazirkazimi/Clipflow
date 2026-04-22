import yt_dlp
import logging
import os

logger = logging.getLogger(__name__)

def fetch_instagram_reel(url: str, download_video=True, output_dir="downloads"):
    """
    Fetches info about an Instagram reel and optionally downloads it.
    Uses yt-dlp which supports Instagram downloads.
    """
    try:
        os.makedirs(output_dir, exist_ok=True)
        
        ydl_opts = {
            'quiet': False,
            'skip_download': not download_video,
            'outtmpl': f'{output_dir}/instagram_%(id)s.%(ext)s',
            'format': 'best[height<=1080]/best',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=download_video)
            
            reel_info = {
                'id': info_dict.get('id'),
                'title': info_dict.get('title', 'Instagram Reel'),
                'duration': info_dict.get('duration'),
                'upload_date': info_dict.get('upload_date'),
                'filepath': f"{output_dir}/instagram_{info_dict.get('id')}.mp4" if download_video else None
            }
            
            print(f"Fetched Instagram Reel: {reel_info['title']} - Duration: {reel_info['duration']}s")
            return reel_info
            
    except Exception as e:
        logger.error(f"Error fetching Instagram reel: {e}")
        return None

if __name__ == "__main__":
    # Test block
    test_url = "https://www.instagram.com/reel/YOUR_REEL_ID/"
    res = fetch_instagram_reel(test_url, download_video=False)
    if res:
        print("Test extraction successful.")
