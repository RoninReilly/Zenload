import asyncio
import logging
import os
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

import aiohttp

logger = logging.getLogger(__name__)

# Cloudflare Worker URL for SoundCloud API proxy
# This bypasses geo-blocking by routing requests through Cloudflare's network
SOUNDCLOUD_WORKER_URL = os.getenv(
    "SOUNDCLOUD_WORKER_URL",
    "https://soundcloud-proxy.roninreilly.workers.dev"
)


class SoundcloudService:
    """SoundCloud service using Cloudflare Worker proxy for API access."""

    _instance = None

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def get_instance(cls) -> "SoundcloudService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            )
        return self._session

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        """Expose session for downloader compatibility."""
        return self._session

    async def _worker_request(self, endpoint: str, params: Dict[str, str]) -> Optional[Dict]:
        """Make request to Cloudflare Worker."""
        session = await self._get_session()
        url = f"{SOUNDCLOUD_WORKER_URL}{endpoint}?{urlencode(params)}"
        
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    logger.error(f"Worker error {resp.status}: {text[:200]}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Worker request timeout: {endpoint}")
            return None
        except Exception as e:
            logger.error(f"Worker request error: {e}")
            return None

    def _normalize_track(self, track: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize track data to standard format."""
        user = track.get("user") or {}
        media = track.get("media") or {}
        
        # Find progressive stream URL from transcodings
        stream_url = None
        transcodings = media.get("transcodings") or []
        for t in transcodings:
            fmt = t.get("format") or {}
            if fmt.get("protocol") == "progressive":
                # This is the transcoding URL, not the final stream URL
                # We'll need to call /stream to get the actual URL
                break
        
        return {
            "id": track.get("id"),
            "title": track.get("title") or "SoundCloud Track",
            "kind": "track",
            "permalink_url": track.get("permalink_url"),
            "duration": track.get("duration", 0),  # already in ms
            "full_duration": track.get("duration", 0),
            "artwork_url": track.get("artwork_url"),
            "playback_count": track.get("playback_count"),
            "user": {
                "username": user.get("username"),
                "full_name": user.get("full_name"),
            },
            "media": media,
            "_stream_url": stream_url,
        }

    async def search_tracks(self, query: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Search tracks using Cloudflare Worker."""
        if not query:
            return []

        data = await self._worker_request("/search", {"q": query, "limit": str(limit)})
        
        if not data or "tracks" not in data:
            return []
        
        tracks = []
        for track in data["tracks"]:
            tracks.append(self._normalize_track(track))
        
        logger.info(f"SoundCloud search '{query}' -> {len(tracks)} tracks")
        return tracks

    async def resolve_track(self, url: str) -> Optional[Dict[str, Any]]:
        """Resolve a SoundCloud URL into track metadata."""
        data = await self._worker_request("/resolve", {"url": url})
        
        if not data or "track" not in data:
            return None
        
        return self._normalize_track(data["track"])

    async def get_stream_url(self, track: Dict[str, Any]) -> Optional[str]:
        """
        Get direct stream URL for a track.
        Uses the Worker's /stream endpoint which returns the actual MP3 URL.
        """
        # Check if we already have a cached stream URL
        if track.get("_stream_url"):
            return track["_stream_url"]
        
        # Get track URL
        track_url = track.get("permalink_url")
        if not track_url:
            return None
        
        # Call worker to get stream URL
        data = await self._worker_request("/stream", {"url": track_url})
        
        if not data or "url" not in data:
            return None
        
        return data["url"]

    async def close(self):
        """Close underlying sessions."""
        try:
            if self._session and not self._session.closed:
                await asyncio.wait_for(self._session.close(), timeout=3)
        except Exception as e:
            logger.warning(f"Error closing SoundCloud session: {e}")
        finally:
            self._session = None
