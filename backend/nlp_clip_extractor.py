import requests
import json
import logging
import math

logger = logging.getLogger(__name__)

HOOK_KEYWORDS = {'secret', 'mistake', 'why', 'stop', 'listen', 'look', 'never', 'always', 'truth', 'reason', 'hack', 'trick', 'illegal', 'crazy'}
VALUE_KEYWORDS = {'step', 'first', 'how', 'because', 'this means', 'if you', 'process', 'method', 'doing', 'example'}
PAYOFF_KEYWORDS = {'result', 'double', 'money', 'views', 'growth', 'massive', 'win', 'success', 'boom', 'easy', 'fast', 'free'}

def fetch_youtube_transcript(info_dict):
    """
    Attempts to fetch the JSON3 automatic captions from yt-dlp info_dict.
    Returns a list of dicts: [{'start': 0.0, 'end': 1.0, 'text': 'hello world'}]
    """
    captions = info_dict.get('automatic_captions', {})
    if not captions:
        return []
    
    # Prefer English, fallback to Hindi, then whatever is first
    lang = 'en'
    if lang not in captions:
        lang = 'hi' if 'hi' in captions else list(captions.keys())[0]
        
    subs = captions[lang]
    json3_url = None
    for sub in subs:
        if sub.get('ext') == 'json3':
            json3_url = sub.get('url')
            break
            
    if not json3_url:
        return []
        
    try:
        response = requests.get(json3_url, timeout=10)
        data = response.json()
        
        transcript = []
        for event in data.get('events', []):
            start_ms = event.get('tStartMs', 0)
            duration_ms = event.get('dDurationMs', 0)
            segs = event.get('segs', [])
            
            text = "".join([seg.get('utf8', '') for seg in segs]).replace('\n', ' ').strip()
            if text:
                transcript.append({
                    'start': start_ms / 1000.0,
                    'end': (start_ms + duration_ms) / 1000.0,
                    'text': text.lower()
                })
        return transcript
    except Exception as e:
        logger.error(f"Failed to fetch JSON3 transcript: {e}")
        return []

def score_segment_nlp(transcript, start_time, duration):
    """
    Scores a time segment based on the Hook -> Value -> Payoff structure
    and speech density (words per second).
    """
    end_time = start_time + duration
    segment_words = []
    
    for item in transcript:
        if item['start'] >= start_time and item['end'] <= end_time:
            segment_words.extend(item['text'].split())
            
    if not segment_words:
        return 0
        
    word_count = len(segment_words)
    wps = word_count / duration  # words per second
    
    # High words per second usually means high energy/fast talking
    density_score = min(wps / 2.5, 1.0) * 30  # Cap at 30 points
    
    hook_score = sum(1 for w in segment_words if w in HOOK_KEYWORDS) * 15
    value_score = sum(1 for w in segment_words if w in VALUE_KEYWORDS) * 10
    payoff_score = sum(1 for w in segment_words if w in PAYOFF_KEYWORDS) * 15
    
    # The ideal clip has all three elements (Hook, Value, Payoff)
    structure_bonus = 0
    if hook_score > 0 and value_score > 0 and payoff_score > 0:
        structure_bonus = 30  # Perfect structure bonus
        
    total_score = density_score + hook_score + value_score + payoff_score + structure_bonus
    return min(total_score, 100.0)

def find_nlp_clips(info_dict, num_clips=3, clip_duration=30.0, heatmap_moments=None):
    """
    Analyzes the transcript to find the highest scoring clips based on NLP.
    If heatmap_moments is provided, it drastically boosts the score of segments
    that are close to the heatmap peaks, giving you the best of both worlds
    (Structural Hook + Audience Retention).
    """
    transcript = fetch_youtube_transcript(info_dict)
    if not transcript:
        return []
        
    total_duration = info_dict.get('duration', 0)
    if total_duration <= clip_duration:
        return [{'start_time': 0, 'value': 100.0}]
        
    # Get highest heatmap peaks to boost NLP scores
    heatmap_peaks = []
    if heatmap_moments:
        # Find the top 10 peaks to use as general areas of interest
        sorted_heatmap = sorted(heatmap_moments, key=lambda x: x.get('value', 0), reverse=True)
        heatmap_peaks = [m['start_time'] for m in sorted_heatmap[:10]]
        
    # Sliding window to score clips every 2.5 seconds (tighter search for perfect hooks)
    step = 2.5
    possible_clips = []
    
    for start_time in range(0, int(total_duration - clip_duration), int(step)):
        score = score_segment_nlp(transcript, start_time, clip_duration)
        
        # Boost score massively if this hook is near a known viral heatmap peak!
        if heatmap_peaks:
            for peak in heatmap_peaks:
                # If this clip starts near a peak (within 15 seconds)
                if abs(start_time - peak) <= 15:
                    score += 50.0 # Huge bonus for intersecting with human retention data
                    break
                    
        if score > 10: # Minimum viable score
            possible_clips.append({'start_time': start_time, 'value': score})
            
    # Sort by score descending
    possible_clips.sort(key=lambda x: x['value'], reverse=True)
    
    # Filter out overlapping clips
    selected_clips = []
    for clip in possible_clips:
        if len(selected_clips) >= num_clips:
            break
            
        overlap = False
        for selected in selected_clips:
            if abs(clip['start_time'] - selected['start_time']) < clip_duration:
                overlap = True
                break
                
        if not overlap:
            selected_clips.append(clip)
            
    return selected_clips
