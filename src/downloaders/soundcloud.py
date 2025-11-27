import logging
import re
from pathlib import Path
from typing import Tuple, Dict, List

from streamrip.exceptions import NonStreamableError

from .base import BaseDownloader, DownloadError
from ..config import DOWNLOADS_DIR
from ..utils.soundcloud_service import SoundcloudService

logger = logging.getLogger(__name__)


class SoundcloudDownloader(BaseDownloader):
    """Downloader powered by streamrip's SoundCloud client."""

    _url_pattern = re.compile(r"(soundcloud\.com|sndcdn\.com)", re.IGNORECASE)

    def __init__(self):
        super().__init__()
        self.service = SoundcloudService.get_instance()

    def platform_id(self) -> str:
        return "soundcloud"

    def can_handle(self, url: str) -> bool:
        return bool(url and self._url_pattern.search(url))

    async def get_formats(self, url: str) -> List[Dict]:
        # SoundCloud public API only exposes a single mp3-ish stream
        return [
            {
                "id": "mp3",
                "quality": "MP3 128-160 kbps",
                "ext": "mp3",
            }
        ]

    async def _get_track_info(self, url: str) -> Tuple[Dict, Path, object]:
        """Resolve URL, get downloadable, and compute target path."""
        track_meta = await self.service.resolve_track(url)
        if not track_meta or track_meta.get("kind") != "track":
            raise DownloadError("Track not found or unsupported")

        downloadable = await self.service.get_downloadable(track_meta["id"])
        ext = downloadable.extension or "mp3"

        title = track_meta.get("title") or "SoundCloud Track"
        artist = ""
        user_info = track_meta.get("user") or {}
        if isinstance(user_info, dict):
            artist = user_info.get("username") or user_info.get("full_name") or ""

        filename = f"{artist + ' - ' if artist else ''}{title}.{ext}"
        safe_name = self._prepare_filename(filename)
        file_path = DOWNLOADS_DIR / safe_name
        return track_meta, file_path, downloadable

    def _format_metadata(self, track_meta: Dict) -> str:
        parts = []
        title = track_meta.get("title")
        if title:
            parts.append(title)

        user_info = track_meta.get("user") or {}
        artist = user_info.get("username") or user_info.get("full_name")
        if artist:
            parts.append(f"By: {artist}")

        duration_ms = track_meta.get("duration") or track_meta.get("full_duration")
        if duration_ms:
            minutes = int(duration_ms) // 60000
            seconds = int(duration_ms) % 60000 // 1000
            parts.append(f"Length: {minutes}:{seconds:02d}")

        play_count = track_meta.get("playback_count")
        if play_count:
            if play_count >= 1_000_000:
                parts.append(f"Plays: {play_count/1_000_000:.1f}M")
            elif play_count >= 1_000:
                parts.append(f"Plays: {play_count/1_000:.1f}K")
            else:
                parts.append(f"Plays: {play_count}")

        permalink = track_meta.get("permalink_url")
        if permalink:
            parts.append(permalink)

        return " | ".join(parts)

    async def download(self, url: str, format_id: str = None) -> Tuple[str, Path]:
        try:
            self.update_progress("status_downloading", 5)
            track_meta, file_path, downloadable = await self._get_track_info(url)

            total_size = await downloadable.size()
            downloaded = 0

            def progress_cb(chunk_size: int):
                nonlocal downloaded, total_size
                downloaded += chunk_size
                if total_size:
                    progress = min(100, max(10, int(downloaded / total_size * 90)))
                    self.update_progress("status_downloading", progress)

            await downloadable.download(str(file_path), progress_cb)
            self.update_progress("status_downloading", 100)

            metadata = self._format_metadata(track_meta)
            return metadata, file_path
        except NonStreamableError as e:
            raise DownloadError(f"Track is not streamable: {e}")
        except Exception as e:
            logger.error(f"Error downloading from SoundCloud: {e}", exc_info=True)
            raise DownloadError(f"Download error: {e}")
