#!/usr/bin/env python3
"""
Standalone test script for Instagram and Yandex Music downloaders.
Run without Telegram bot to verify downloaders work.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test URLs
INSTAGRAM_URLS = [
    "https://www.instagram.com/reel/DRkN17kjH16/?igsh=MXNpZXg3dXFpdHM5cg==",
    "https://www.instagram.com/reel/DRZHg84jN1Z/?igsh=MTgzbWoyM2R2aXJpeQ==",
]

YANDEX_URLS = [
    "https://music.yandex.ru/track/143091515",
    "https://music.yandex.ru/track/144942084",
]


class MockDownloader:
    """Base class with mock progress update for standalone testing"""
    def update_progress(self, status: str, progress: int):
        logger.info(f"Progress: {status} - {progress}%")
    
    def _prepare_filename(self, name: str) -> str:
        """Prepare safe filename"""
        import re
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        return name[:100]


async def test_instagram():
    """Test Instagram downloader"""
    print("\n" + "="*60)
    print("🔍 TESTING INSTAGRAM DOWNLOADER")
    print("="*60)
    
    # Import the downloader parts we need
    import os
    import re
    import json
    import requests
    
    # Create downloads directory
    downloads_dir = Path(__file__).parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    
    for url in INSTAGRAM_URLS:
        print(f"\n📌 Testing URL: {url}")
        print("-" * 50)
        
        # Extract shortcode
        shortcode = None
        patterns = [
            r'instagram\.com/p/([A-Za-z0-9_-]+)',
            r'instagram\.com/reel/([A-Za-z0-9_-]+)',
            r'instagram\.com/reels/([A-Za-z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                shortcode = match.group(1)
                break
        
        if not shortcode:
            print("❌ Could not extract shortcode")
            continue
        
        print(f"✓ Shortcode: {shortcode}")
        
        # Test embed method
        print("\n📦 Method 1: Embed endpoint")
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
        print(f"  Fetching: {embed_url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
            }
            response = requests.get(embed_url, headers=headers, timeout=15)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                html = response.text
                
                # Try patterns
                video_url = None
                
                # Pattern 1: video_url in JSON
                match = re.search(r'"video_url"\s*:\s*"([^"]+)"', html)
                if match:
                    video_url = match.group(1).replace('\\u0026', '&').replace('\\/', '/')
                    print(f"  ✓ Found video_url in JSON")
                
                # Pattern 2: og:video
                if not video_url:
                    match = re.search(r'<meta[^>]+property="og:video"[^>]+content="([^"]+)"', html)
                    if match:
                        video_url = match.group(1).replace('&amp;', '&')
                        print(f"  ✓ Found og:video meta tag")
                
                # Pattern 3: video src
                if not video_url:
                    match = re.search(r'<video[^>]+src="([^"]+)"', html)
                    if match:
                        video_url = match.group(1).replace('&amp;', '&')
                        print(f"  ✓ Found video src tag")
                
                if video_url:
                    print(f"  Video URL: {video_url[:80]}...")
                    
                    # Try to download
                    print("  Downloading...")
                    vid_response = requests.get(video_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
                    if vid_response.status_code == 200:
                        file_path = downloads_dir / f"{shortcode}_embed.mp4"
                        with open(file_path, 'wb') as f:
                            f.write(vid_response.content)
                        size_mb = len(vid_response.content) / (1024 * 1024)
                        print(f"  ✅ Downloaded: {file_path.name} ({size_mb:.2f} MB)")
                    else:
                        print(f"  ❌ Download failed: {vid_response.status_code}")
                else:
                    print("  ⚠️ No video URL found in embed")
            else:
                print(f"  ❌ Embed request failed")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test external service (FastDL)
        print("\n📦 Method 2: External service (FastDL)")
        try:
            fastdl_url = "https://fastdl.app/api/convert"
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'Origin': 'https://fastdl.app',
                'Referer': 'https://fastdl.app/'
            }
            data = {'url': url}
            
            response = requests.post(fastdl_url, headers=headers, data=data, timeout=15)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"  Response keys: {list(result.keys())}")
                
                video_url = result.get('url') or result.get('video')
                if video_url:
                    print(f"  ✓ Got video URL from FastDL")
                    print(f"  Video URL: {video_url[:80]}...")
                    
                    # Try to download
                    print("  Downloading...")
                    vid_response = requests.get(video_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
                    if vid_response.status_code == 200:
                        file_path = downloads_dir / f"{shortcode}_fastdl.mp4"
                        with open(file_path, 'wb') as f:
                            f.write(vid_response.content)
                        size_mb = len(vid_response.content) / (1024 * 1024)
                        print(f"  ✅ Downloaded: {file_path.name} ({size_mb:.2f} MB)")
                    else:
                        print(f"  ❌ Download failed: {vid_response.status_code}")
                else:
                    print(f"  ⚠️ No video URL in response: {result}")
            else:
                print(f"  ❌ FastDL request failed: {response.text[:200]}")
        except Exception as e:
            print(f"  ❌ Error: {e}")


async def test_yandex():
    """Test Yandex Music downloader (YouTube fallback)"""
    print("\n" + "="*60)
    print("🔍 TESTING YANDEX MUSIC DOWNLOADER (YouTube fallback)")
    print("="*60)
    
    import re
    import requests
    import yt_dlp
    
    downloads_dir = Path(__file__).parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)
    
    for url in YANDEX_URLS:
        print(f"\n📌 Testing URL: {url}")
        print("-" * 50)
        
        # Extract track ID
        match = re.search(r'track/(\d+)', url)
        if not match:
            print("❌ Could not extract track ID")
            continue
        
        track_id = match.group(1)
        print(f"✓ Track ID: {track_id}")
        
        # First, try to get track name from the page
        print("\n📦 Step 1: Fetching track info from page...")
        clean_url = url.split('?')[0]
        
        search_query = None
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8',
            }
            response = requests.get(clean_url, headers=headers, timeout=15)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                html = response.text
                title = None
                artist = None
                
                # Try og:title (track name)
                og_title = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html)
                if og_title:
                    title = og_title.group(1)
                    print(f"  ✓ Found og:title: {title}")
                
                # Try og:description (format: "Artist • Трек • Year")
                og_desc = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"', html)
                if og_desc:
                    desc = og_desc.group(1)
                    print(f"  ✓ Found og:description: {desc}")
                    parts = desc.split('•')
                    if parts:
                        artist = parts[0].strip()
                        print(f"  ✓ Extracted artist: {artist}")
                
                # Build query
                if title and artist:
                    search_query = f"{artist} - {title}"
                elif title:
                    search_query = title
        except Exception as e:
            print(f"  ❌ Error fetching page: {e}")
        
        if not search_query:
            print("  ⚠️ Could not extract track info, skipping YouTube search")
            continue
        
        # Now search on YouTube
        print(f"\n📦 Step 2: Searching YouTube for: {search_query}")
        
        try:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(downloads_dir / f"yandex_{track_id}.%(ext)s"),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'nooverwrites': True,
                'no_color': True,
                'quiet': False,
                'default_search': 'ytsearch1',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print("  Extracting info...")
                info = ydl.extract_info(f"ytsearch1:{search_query}", download=True)
                
                if info and 'entries' in info and len(info['entries']) > 0:
                    entry = info['entries'][0]
                    title = entry.get('title', 'Unknown')
                    channel = entry.get('uploader', 'Unknown')
                    print(f"  ✅ Found: {title}")
                    print(f"     Channel: {channel}")
                    
                    # Check for downloaded file
                    for f in downloads_dir.glob(f"yandex_{track_id}.*"):
                        size_mb = f.stat().st_size / (1024 * 1024)
                        print(f"  ✅ Downloaded: {f.name} ({size_mb:.2f} MB)")
                        break
                else:
                    print("  ❌ No results found")
                    
        except Exception as e:
            print(f"  ❌ Error: {e}")


async def main():
    print("🚀 ZENLOAD DOWNLOADER TEST")
    print("=" * 60)
    print("This script tests downloaders without running Telegram bot")
    print()
    
    # Check dependencies
    try:
        import requests
        print("✓ requests installed")
    except ImportError:
        print("❌ requests not installed: pip install requests")
        sys.exit(1)
    
    try:
        import yt_dlp
        print("✓ yt-dlp installed")
    except ImportError:
        print("❌ yt-dlp not installed: pip install yt-dlp")
        sys.exit(1)
    
    # Run tests
    await test_instagram()
    await test_yandex()
    
    print("\n" + "="*60)
    print("✅ TEST COMPLETE")
    print("="*60)
    print(f"\nDownloaded files are in: {Path(__file__).parent / 'downloads'}")


if __name__ == "__main__":
    asyncio.run(main())
