import asyncio
import logging
from typing import List, Dict, Any

from streamrip.config import Config
from streamrip.client.soundcloud import SoundcloudClient

from ..config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)


class SoundcloudService:
    """Thin wrapper around streamrip's Soundcloud client for search/resolve/downloadable."""

    _instance = None

    def __init__(self):
        self.config = Config.defaults()
        # Keep downloads inside our app directory
        self.config.session.downloads.folder = str(DOWNLOADS_DIR)
        self.config.file.downloads.folder = str(DOWNLOADS_DIR)

        self.client = SoundcloudClient(self.config)
        self._login_lock = asyncio.Lock()
        self._logged_in = False

    @classmethod
    def get_instance(cls) -> "SoundcloudService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def ensure_logged_in(self):
        if self._logged_in and self.client.session and not self.client.session.closed:
            return

        async with self._login_lock:
            if self._logged_in and self.client.session and not self.client.session.closed:
                return
            await self.client.login()
            self._logged_in = True
            logger.info("SoundCloud client logged in with public tokens")

    async def search_tracks(self, query: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Search tracks and return streamrip track dicts (with composite ids)."""
        await self.ensure_logged_in()
        if not query:
            return []
        results = await self.client.search("track", query, limit=limit)
        if not results:
            return []
        return results[0].get("collection", [])

    async def resolve_track(self, url: str) -> Dict[str, Any]:
        """Resolve a SoundCloud URL into track metadata (id contains download info)."""
        await self.ensure_logged_in()
        return await self.client.resolve_url(url)

    async def get_track_metadata(self, track_id: str) -> Dict[str, Any]:
        """Get full metadata by composite track id."""
        await self.ensure_logged_in()
        return await self.client.get_metadata(track_id, "track")

    async def get_downloadable(self, track_id: str):
        """Get streamrip Downloadable for a track id (composite)."""
        await self.ensure_logged_in()
        return await self.client.get_downloadable(
            track_id,
            self.config.session.soundcloud.quality,
        )

    async def get_stream_url(self, track: Dict[str, Any]) -> str | None:
        """
        Return a direct stream URL, preferring progressive mp3 if available.
        """
        await self.ensure_logged_in()
        media = (track or {}).get("media", {})
        transcodings = media.get("transcodings") or []

        progressive = next(
            (
                t
                for t in transcodings
                if t.get("format", {}).get("protocol") == "progressive"
            ),
            None,
        )
        target = progressive or (transcodings[0] if transcodings else None)
        if not target:
            return None

        try:
            resp, status = await self.client._request(target["url"])  # type: ignore[attr-defined]
            if status == 200:
                return resp.get("url")
        except Exception as e:
            logger.error(f"Failed to fetch stream URL: {e}")
        return None
