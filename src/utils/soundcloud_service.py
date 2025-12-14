import logging
from typing import List, Dict, Any, Optional, Generator
from concurrent.futures import ThreadPoolExecutor
import asyncio
import aiohttp

from soundcloud import SoundCloud, BasicTrack

logger = logging.getLogger(__name__)


class SoundcloudService:
    """Thin wrapper around soundcloud-v2 library for search/resolve/stream."""

    _instance = None

    def __init__(self):
        self._client: Optional[SoundCloud] = None
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._session: Optional[aiohttp.ClientSession] = None
        self._init_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "SoundcloudService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _ensure_client(self) -> SoundCloud:
        """Lazily initialize the SoundCloud client."""
        if self._client is not None:
            return self._client

        async with self._init_lock:
            if self._client is not None:
                return self._client

            loop = asyncio.get_event_loop()
            # SoundCloud client init is synchronous, run in executor
            self._client = await loop.run_in_executor(
                self._executor,
                lambda: SoundCloud()
            )
            logger.info("SoundCloud client initialized (no auth required)")
            return self._client

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for stream downloads."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        """Expose session for downloader compatibility."""
        return self._session

    def _track_to_dict(self, track: BasicTrack) -> Dict[str, Any]:
        """Convert soundcloud-v2 track object to dict matching old streamrip format."""
        user_dict = {}
        if track.user:
            user_dict = {
                "username": getattr(track.user, "username", None),
                "full_name": getattr(track.user, "full_name", None),
                "permalink": getattr(track.user, "permalink", None),
            }

        transcodings = []
        if track.media and track.media.transcodings:
            for t in track.media.transcodings:
                transcodings.append({
                    "url": t.url,
                    "preset": t.preset,
                    "duration": t.duration,
                    "snipped": t.snipped,
                    "format": {
                        "protocol": t.format.protocol if t.format else None,
                        "mime_type": t.format.mime_type if t.format else None,
                    },
                    "quality": t.quality,
                })

        return {
            "id": track.id,
            "title": track.title,
            "kind": track.kind,
            "permalink_url": track.permalink_url,
            "duration": track.duration,
            "full_duration": track.full_duration,
            "artwork_url": track.artwork_url,
            "playback_count": getattr(track, "playback_count", None),
            "user": user_dict,
            "media": {"transcodings": transcodings},
            "track_authorization": getattr(track, "track_authorization", None),
        }

    async def search_tracks(self, query: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Search tracks and return list of track dicts."""
        if not query:
            return []

        client = await self._ensure_client()
        loop = asyncio.get_event_loop()

        def _search():
            results = []
            try:
                gen: Generator = client.search_tracks(query)
                for i, track in enumerate(gen):
                    if i >= limit:
                        break
                    results.append(self._track_to_dict(track))
            except Exception as e:
                logger.error(f"SoundCloud search error: {e}")
            return results

        tracks = await asyncio.wait_for(
            loop.run_in_executor(self._executor, _search),
            timeout=10
        )
        return tracks

    async def resolve_track(self, url: str) -> Optional[Dict[str, Any]]:
        """Resolve a SoundCloud URL into track metadata."""
        client = await self._ensure_client()
        loop = asyncio.get_event_loop()

        def _resolve():
            try:
                result = client.resolve(url)
                if result and hasattr(result, "kind") and result.kind == "track":
                    return self._track_to_dict(result)
            except Exception as e:
                logger.error(f"SoundCloud resolve error: {e}")
            return None

        return await asyncio.wait_for(
            loop.run_in_executor(self._executor, _resolve),
            timeout=10
        )

    async def get_stream_url(self, track: Dict[str, Any]) -> Optional[str]:
        """
        Return a direct stream URL, preferring progressive mp3 if available.
        """
        client = await self._ensure_client()
        media = track.get("media", {})
        transcodings = media.get("transcodings") or []

        if not transcodings:
            return None

        # Prefer progressive (direct download) over HLS
        progressive = next(
            (t for t in transcodings if t.get("format", {}).get("protocol") == "progressive"),
            None,
        )
        target = progressive or transcodings[0]
        transcoding_url = target.get("url")

        if not transcoding_url:
            return None

        # Need to fetch the actual stream URL from the transcoding endpoint
        # The transcoding URL requires client_id parameter
        try:
            session = await self._get_session()
            params = {"client_id": client.client_id}

            async with session.get(transcoding_url, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("url")
        except Exception as e:
            logger.error(f"Failed to fetch stream URL: {e}")

        return None

    async def close(self):
        """Close underlying sessions."""
        try:
            if self._session and not self._session.closed:
                await asyncio.wait_for(self._session.close(), timeout=3)
        except Exception as e:
            logger.warning(f"Error closing SoundCloud session: {e}")
        finally:
            self._session = None
