import asyncio
import json
import logging
import subprocess
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import aiohttp

logger = logging.getLogger(__name__)


class SoundcloudService:
    """SoundCloud service using yt-dlp for search and stream URLs."""

    _instance = None

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._session: Optional[aiohttp.ClientSession] = None

    @classmethod
    def get_instance(cls) -> "SoundcloudService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session for stream downloads."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        """Expose session for downloader compatibility."""
        return self._session

    def _run_ytdlp(self, args: List[str], timeout: int = 30) -> Optional[str]:
        """Run yt-dlp with given arguments and return stdout."""
        cmd = ["yt-dlp", "--no-warnings"] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            if result.returncode == 0:
                return result.stdout
            logger.error(f"yt-dlp error: {result.stderr}")
        except subprocess.TimeoutExpired:
            logger.error("yt-dlp timeout")
        except Exception as e:
            logger.error(f"yt-dlp exception: {e}")
        return None

    def _parse_track(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert yt-dlp track data to our standard format."""
        # Get best audio format URL for streaming
        formats = data.get("formats", [])
        stream_url = None
        
        # Prefer http progressive over HLS
        for fmt in formats:
            if fmt.get("protocol") == "http" and fmt.get("acodec") != "none":
                stream_url = fmt.get("url")
                break
        
        # Fallback to any audio format
        if not stream_url:
            for fmt in formats:
                if fmt.get("acodec") != "none":
                    stream_url = fmt.get("url")
                    break

        duration_ms = int((data.get("duration") or 0) * 1000)

        return {
            "id": data.get("id"),
            "title": data.get("title") or "SoundCloud Track",
            "kind": "track",
            "permalink_url": data.get("webpage_url") or data.get("url"),
            "duration": duration_ms,
            "full_duration": duration_ms,
            "artwork_url": data.get("thumbnail"),
            "playback_count": data.get("view_count"),
            "user": {
                "username": data.get("uploader"),
                "full_name": data.get("uploader"),
                "permalink": data.get("uploader_id"),
            },
            "media": {
                "transcodings": []  # Not used with yt-dlp approach
            },
            # yt-dlp specific - direct stream URL
            "_stream_url": stream_url,
            "_formats": formats,
        }

    async def search_tracks(self, query: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Search tracks using yt-dlp's scsearch."""
        if not query:
            return []

        loop = asyncio.get_event_loop()

        def _search():
            # scsearch:N searches SoundCloud and returns N results
            args = [
                "--dump-json",
                "--flat-playlist",
                f"scsearch{limit}:{query}"
            ]
            output = self._run_ytdlp(args, timeout=15)
            if not output:
                return []

            tracks = []
            for line in output.strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        # flat-playlist gives minimal info, get URL for full info later
                        track_url = data.get("url") or data.get("webpage_url")
                        if track_url:
                            tracks.append({
                                "id": data.get("id"),
                                "title": data.get("title") or "SoundCloud Track",
                                "kind": "track",
                                "permalink_url": track_url,
                                "duration": int((data.get("duration") or 0) * 1000),
                                "full_duration": int((data.get("duration") or 0) * 1000),
                                "artwork_url": data.get("thumbnail"),
                                "user": {
                                    "username": data.get("uploader"),
                                    "full_name": data.get("uploader"),
                                },
                                "_stream_url": None,  # Will be fetched on demand
                                "_url": track_url,
                            })
                    except json.JSONDecodeError:
                        continue
            return tracks

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._executor, _search),
                timeout=20
            )
        except asyncio.TimeoutError:
            logger.error("SoundCloud search timeout")
            return []

    async def resolve_track(self, url: str) -> Optional[Dict[str, Any]]:
        """Resolve a SoundCloud URL into track metadata with stream URL."""
        loop = asyncio.get_event_loop()

        def _resolve():
            args = [
                "--dump-json",
                "--no-download",
                url
            ]
            output = self._run_ytdlp(args, timeout=20)
            if not output:
                return None
            try:
                data = json.loads(output)
                return self._parse_track(data)
            except json.JSONDecodeError:
                return None

        try:
            return await asyncio.wait_for(
                loop.run_in_executor(self._executor, _resolve),
                timeout=25
            )
        except asyncio.TimeoutError:
            logger.error("SoundCloud resolve timeout")
            return None

    async def get_stream_url(self, track: Dict[str, Any]) -> Optional[str]:
        """
        Get direct stream URL for a track.
        First checks if already cached, otherwise fetches via yt-dlp.
        """
        # Check if we already have stream URL
        stream_url = track.get("_stream_url")
        if stream_url:
            return stream_url

        # Need to fetch full info to get stream URL
        track_url = track.get("_url") or track.get("permalink_url")
        if not track_url:
            return None

        full_track = await self.resolve_track(track_url)
        if full_track:
            return full_track.get("_stream_url")

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
