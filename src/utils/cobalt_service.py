"""
Cobalt API Service - Universal video downloader

Supports: Instagram, TikTok, Twitter/X, YouTube, Reddit, Pinterest, 
Snapchat, Twitch, Vimeo, SoundCloud, Facebook, and more.

Uses public Cobalt instances - NO TOKEN REQUIRED!
Instances are fetched dynamically from instances.cobalt.best
"""

import os
import json
import asyncio
import logging
import subprocess
import random
import time
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Instances API
INSTANCES_API = "https://instances.cobalt.best/api/instances.json"
INSTANCES_CACHE_TTL = 3600  # 1 hour

# Fallback instances if API fails
FALLBACK_INSTANCES = [
    "https://cobalt-api.kwiatekmiki.com/",
    "https://cobalt-backend.canine.tools/",
    "https://capi.3kh0.net/",
]

# Official API (requires token)
OFFICIAL_API = "https://api.cobalt.tools/"
OFFICIAL_TOKEN = os.getenv("COBALT_API_TOKEN", "")

# User agent
USER_AGENT = "zenload/1.0 (+https://github.com/zenload)"

# Supported services
COBALT_SERVICES = {
    "instagram": ["instagram.com", "instagr.am"],
    "tiktok": ["tiktok.com", "vm.tiktok.com"],
    "twitter": ["twitter.com", "x.com", "t.co"],
    "youtube": ["youtube.com", "youtu.be", "music.youtube.com"],
    "reddit": ["reddit.com", "redd.it"],
    "pinterest": ["pinterest.com", "pin.it"],
    "snapchat": ["snapchat.com"],
    "twitch": ["twitch.tv", "clips.twitch.tv"],
    "vimeo": ["vimeo.com"],
    "soundcloud": ["soundcloud.com"],
    "facebook": ["facebook.com", "fb.watch"],
    "bilibili": ["bilibili.com", "b23.tv"],
    "dailymotion": ["dailymotion.com"],
    "rutube": ["rutube.ru"],
    "ok": ["ok.ru"],
    "vk": ["vk.com"],
    "tumblr": ["tumblr.com"],
    "streamable": ["streamable.com"],
    "loom": ["loom.com"],
    "bluesky": ["bsky.app"],
}


@dataclass
class CobaltResult:
    """Result from Cobalt API"""
    success: bool
    url: Optional[str] = None
    filename: Optional[str] = None
    error: Optional[str] = None
    picker: Optional[list] = None


class CobaltService:
    """Universal Cobalt API client with dynamic instance discovery"""
    
    def __init__(self):
        self._instances: List[str] = []
        self._instances_updated: float = 0
        self._current_index: int = 0
        self._failed_instances: set = set()
    
    async def _fetch_instances(self) -> List[str]:
        """Fetch public instances from API"""
        try:
            cmd = [
                'curl', '-s', INSTANCES_API,
                '-H', f'User-Agent: {USER_AGENT}',
                '--max-time', '10'
            ]
            
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=15
            )
            
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                instances = []
                
                for item in data:
                    # Get API URL
                    api = item.get('api') or item.get('api_url')
                    if not api:
                        continue
                    
                    # Normalize URL
                    if not api.startswith('http'):
                        api = f"https://{api}"
                    if not api.endswith('/'):
                        api += '/'
                    
                    # Only use trusted instances with CORS
                    if item.get('trust', 0) >= 1 and item.get('cors', False):
                        instances.append(api)
                
                if instances:
                    logger.info(f"[Cobalt] Fetched {len(instances)} public instances")
                    return instances
                    
        except Exception as e:
            logger.warning(f"[Cobalt] Failed to fetch instances: {e}")
        
        return FALLBACK_INSTANCES.copy()
    
    async def _get_instances(self) -> List[str]:
        """Get instances with caching"""
        now = time.time()
        
        # Refresh if cache expired or empty
        if not self._instances or (now - self._instances_updated) > INSTANCES_CACHE_TTL:
            self._instances = await self._fetch_instances()
            self._instances_updated = now
            self._failed_instances.clear()
            random.shuffle(self._instances)
        
        # Filter out recently failed instances
        available = [i for i in self._instances if i not in self._failed_instances]
        
        # Reset failed if all failed
        if not available:
            self._failed_instances.clear()
            available = self._instances.copy()
        
        return available
    
    def _get_next_instance(self, instances: List[str]) -> str:
        """Get next instance (round-robin)"""
        if not instances:
            return FALLBACK_INSTANCES[0]
        instance = instances[self._current_index % len(instances)]
        self._current_index += 1
        return instance
    
    @staticmethod
    def can_handle(url: str) -> bool:
        """Check if URL is supported by Cobalt"""
        url_lower = url.lower()
        for domains in COBALT_SERVICES.values():
            for domain in domains:
                if domain in url_lower:
                    return True
        return False
    
    @staticmethod
    def get_service_name(url: str) -> Optional[str]:
        """Get service name from URL"""
        url_lower = url.lower()
        for service, domains in COBALT_SERVICES.items():
            for domain in domains:
                if domain in url_lower:
                    return service
        return None

    async def _make_request(self, api_url: str, payload: dict, use_token: bool = False) -> Optional[dict]:
        """Make request to Cobalt API"""
        payload_json = json.dumps(payload)
        
        headers = [
            '-H', 'accept: application/json',
            '-H', 'content-type: application/json',
            '-H', f'User-Agent: {USER_AGENT}',
        ]
        
        if use_token and OFFICIAL_TOKEN:
            headers.extend([
                '-H', f'authorization: Bearer {OFFICIAL_TOKEN}',
                '-H', 'origin: https://cobalt.tools',
                '-H', 'referer: https://cobalt.tools/',
            ])
        
        cmd = ['curl', '-s', api_url] + headers + [
            '--data-raw', payload_json,
            '--max-time', '20'
        ]
        
        try:
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True, timeout=25
            )
            if result.returncode == 0 and result.stdout:
                return json.loads(result.stdout)
        except Exception as e:
            logger.debug(f"[Cobalt] Request failed: {e}")
        return None

    async def request(
        self, 
        url: str, 
        video_quality: str = "1080",
        audio_format: str = "mp3",
        download_mode: str = "auto",
        tiktok_watermark: bool = False,
    ) -> CobaltResult:
        """Make request to Cobalt API with automatic instance failover"""
        payload = {
            "url": url,
            "videoQuality": video_quality,
            "audioFormat": audio_format,
            "downloadMode": download_mode,
            "tiktokFullAudio": True,
            "twitterGif": True,
        }
        
        # Get available instances
        instances = await self._get_instances()
        
        # Try up to 3 instances
        for attempt in range(min(3, len(instances))):
            instance = self._get_next_instance(instances)
            logger.info(f"[Cobalt] Trying: {instance}")
            
            data = await self._make_request(instance, payload)
            
            if data:
                status = data.get("status")
                
                if status in ("redirect", "tunnel"):
                    return CobaltResult(
                        success=True,
                        url=data.get("url"),
                        filename=data.get("filename")
                    )
                elif status == "picker":
                    return CobaltResult(
                        success=True,
                        picker=data.get("picker", []),
                        filename=data.get("filename")
                    )
                elif status == "error":
                    error = data.get("error", {})
                    code = error.get("code") if isinstance(error, dict) else str(error)
                    # Content errors - don't retry
                    if any(x in str(code) for x in ["content", "unavailable", "private"]):
                        return CobaltResult(success=False, error=code)
            
            # Mark as failed for this session
            self._failed_instances.add(instance)
        
        # Fallback to official API
        if OFFICIAL_TOKEN:
            logger.info("[Cobalt] Trying official API")
            data = await self._make_request(OFFICIAL_API, payload, use_token=True)
            
            if data:
                status = data.get("status")
                if status in ("redirect", "tunnel"):
                    return CobaltResult(success=True, url=data.get("url"), filename=data.get("filename"))
                elif status == "picker":
                    return CobaltResult(success=True, picker=data.get("picker", []))
                elif status == "error":
                    error = data.get("error", {})
                    return CobaltResult(success=False, error=error.get("code") if isinstance(error, dict) else str(error))
        
        return CobaltResult(success=False, error="All instances failed")

    async def download(
        self, 
        url: str, 
        download_dir: Path,
        progress_callback=None,
        **kwargs
    ) -> Tuple[Optional[str], Optional[Path]]:
        """Download media from URL"""
        import requests
        
        service = self.get_service_name(url)
        logger.info(f"[Cobalt] Downloading from {service}: {url}")
        
        if progress_callback:
            progress_callback('status_downloading', 10)
        
        result = await self.request(url, **kwargs)
        
        if not result.success:
            logger.error(f"[Cobalt] Error: {result.error}")
            return None, None
        
        # Handle picker
        if result.picker:
            for item in result.picker:
                if item.get("type") == "video":
                    result.url = item.get("url")
                    break
            if not result.url and result.picker:
                result.url = result.picker[0].get("url")
        
        if not result.url:
            return None, None
        
        if progress_callback:
            progress_callback('status_downloading', 30)
        
        # Download
        try:
            response = await asyncio.to_thread(
                requests.get,
                result.url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=180
            )
            
            if response.status_code != 200:
                return None, None
            
            if progress_callback:
                progress_callback('status_downloading', 80)
            
            filename = result.filename or f"{service}_{hash(url) % 100000}.mp4"
            download_dir.mkdir(exist_ok=True)
            file_path = download_dir / filename
            
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            if progress_callback:
                progress_callback('status_downloading', 100)
            
            logger.info(f"[Cobalt] Downloaded: {file_path} ({len(response.content)/1024/1024:.1f} MB)")
            return filename, file_path
            
        except Exception as e:
            logger.error(f"[Cobalt] Download error: {e}")
            return None, None


# Global instance
cobalt = CobaltService()
