import re

def extract_video_id(url):
    """
    Extracts the 11-character YouTube video ID from a URL.
    Returns the original string if no pattern matches (assuming it might already be an ID).
    """
    if not url:
        return ""
    
    # Regex covers: youtube.com/watch?v=, youtu.be/, embed/, etc.
    regex = r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})'
    match = re.search(regex, str(url))
    
    if match:
        return match.group(1)
    return str(url).strip()