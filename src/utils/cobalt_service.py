"""
Cobalt API Service - Universal video downloader

Supports: Instagram, TikTok, Twitter/X, YouTube, Reddit, Pinterest, 
Snapchat, Twitch, Vimeo, SoundCloud, Facebook, and more.

Configuration:
- Set COBALT_API_TOKEN in .env to use official API (Recommended)
- Without token, it tries public instances (currently unreliable)
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

# Official API (requires token)
OFFICIAL_API = "https://api.cobalt.tools/"
OFFICIAL_TOKEN = os.getenv("COBALT_API_TOKEN", "")

# Fallback instances
FALLBACK_INSTANCES = [
    "https://cobalt-backend.canine.tools/",
    "https://cobalt-api.kwiatekmiki.com/",
    "https://capi.3kh0.net/",
    "https://cobalt-api.meowing.de/",
    "https://kityune.imput.net/",
    "https://nachos.imput.net/",
    "https://sunny.imput.net/",
    "https://blossom.imput.net/",
    "https://cobalt-7.kwiatekmiki.com/",
    "https://downloadapi.stuff.solutions/",
]

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
    """Universal Cobalt API client"""
    
    def __init__(self):
        self._instances: List[str] = []
        self._instances_updated: float = 0
        self._current_index: int = 0
        self._failed_instances: set = set()
    
    def _get_random_user_agent(self) -> str:
        agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "zenload/1.0 (+https://github.com/zenload)",
        ]
        return random.choice(agents)

    async def _fetch_instances(self) -> List[str]:
        """Fetch public instances from API"""
        try:
            cmd = [
                'curl', '-s', INSTANCES_API,
                '-H', f'User-Agent: {self._get_random_user_agent()}',
                '--max-time', '10'
            ]
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout)
                instances = []
                for item in data:
                    api = item.get('api') or item.get('api_url')
                    if api and item.get('trust', 0) >= 1 and item.get('cors', False):
                        if not api.startswith('http'): api = f"https://{api}"
                        if not api.endswith('/'): api += '/'
                        instances.append(api)
                if instances: return instances
        except:
            pass
        return FALLBACK_INSTANCES.copy()
    
    async def _get_instances(self) -> List[str]:
        now = time.time()
        if not self._instances or (now - self._instances_updated) > INSTANCES_CACHE_TTL:
            fetched = await self._fetch_instances()
            self._instances = list(set(fetched + FALLBACK_INSTANCES))
            self._instances_updated = now
            self._failed_instances.clear()
            random.shuffle(self._instances)
        
        available = [i for i in self._instances if i not in self._failed_instances]
        if not available:
            self._failed_instances.clear()
            available = self._instances.copy()
            random.shuffle(available)
        return available

    async def _make_request(self, api_url: str, payload: dict, use_token: bool = False) -> Optional[dict]:
        payload_json = json.dumps(payload)
        headers = [
            '-H', 'accept: application/json',
            '-H', 'content-type: application/json',
            '-H', f'User-Agent: {self._get_random_user_agent()}',
            '-H', f'Origin: {api_url.rstrip("/")}',
            '-H', f'Referer: {api_url}',
        ]
        
        if use_token and OFFICIAL_TOKEN:
            headers.extend([
                '-H', f'authorization: Bearer {OFFICIAL_TOKEN}',
                '-H', 'origin: https://cobalt.tools',
                '-H', 'referer: https://cobalt.tools/',
            ])
        
        cmd = ['curl', '-s', api_url] + headers + ['--data-raw', payload_json, '--max-time', '25']
        
        try:
            result = await asyncio.to_thread(subprocess.run, cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout:
                if result.stdout.strip().startswith('<'): return None # HTML/Cloudflare
                try: return json.loads(result.stdout)
                except: pass
        except: pass
        return None

    async def request(self, url: str, **kwargs) -> CobaltResult:
        """Make request to Cobalt API"""
        payload = {
            "url": url,
            "videoQuality": kwargs.get("video_quality", "1080"),
            "audioFormat": kwargs.get("audio_format", "mp3"),
            "downloadMode": kwargs.get("download_mode", "auto"),
            "tiktokFullAudio": True,
            "twitterGif": True,
        }
        
        # 1. Try Official API if token exists (Most Reliable)
        if OFFICIAL_TOKEN:
            logger.info("[Cobalt] Using official API with token")
            data = await self._make_request(OFFICIAL_API, payload, use_token=True)
            if data:
                if data.get("status") in ("redirect", "tunnel"):
                    return CobaltResult(success=True, url=data.get("url"), filename=data.get("filename"))
                elif data.get("status") == "picker":
                    return CobaltResult(success=True, picker=data.get("picker", []))
                elif data.get("status") == "error":
                    return CobaltResult(success=False, error=data.get("error", {}).get("code"))

        # 2. Try Public Instances (Fallback)
        instances = await self._get_instances()
        max_attempts = 5
        
        for attempt in range(min(max_attempts, len(instances))):
            instance = instances[attempt]
            logger.info(f"[Cobalt] Trying instance {attempt+1}: {instance}")
            
            data = await self._make_request(instance, payload)
            
            if data:
                status = data.get("status")
                if status in ("redirect", "tunnel"):
                    return CobaltResult(success=True, url=data.get("url"), filename=data.get("filename"))
                elif status == "picker":
                    return CobaltResult(success=True, picker=data.get("picker", []))
                elif status == "error":
                    code = data.get("error", {}).get("code")
                    if any(x in str(code) for x in ["content", "unavailable", "private"]):
                        return CobaltResult(success=False, error=code)
            
            self._failed_instances.add(instance)
        
        return CobaltResult(success=False, error="All instances failed")

    async def download(self, url: str, download_dir: Path, progress_callback=None, **kwargs) -> Tuple[Optional[str], Optional[Path]]:
        import requests
        service = self.get_service_name(url) or "video"
        
        if progress_callback: progress_callback('status_downloading', 10)
        
        result = await self.request(url, **kwargs)
        
        if not result.success:
            logger.warning(f"[Cobalt] Failed: {result.error}")
            return None, None
            
        if result.picker:
            result.url = result.picker[0].get("url")
            
        if not result.url: return None, None
        
        if progress_callback: progress_callback('status_downloading', 30)
        
        try:
            response = await asyncio.to_thread(requests.get, result.url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=180)
            if response.status_code != 200: return None, None
            
            filename = result.filename or f"{service}_{hash(url) % 100000}.mp4"
            download_dir.mkdir(exist_ok=True)
            file_path = download_dir / filename
            
            with open(file_path, 'wb') as f: f.write(response.content)
            
            if progress_callback: progress_callback('status_downloading', 100)
            return filename, file_path
        except Exception as e:
            logger.error(f"[Cobalt] Download error: {e}")
            return None, None

    @staticmethod
    def can_handle(url: str) -> bool:
        return any(d in url.lower() for domains in COBALT_SERVICES.values() for d in domains)
    
    @staticmethod
    def get_service_name(url: str) -> Optional[str]:
        for service, domains in COBALT_SERVICES.items():
            if any(d in url.lower() for d in domains): return service
        return None

cobalt = CobaltService()
