"""Instagram downloader using Cobalt API"""

import re
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict

from .base import BaseDownloader, DownloadError
from ..utils.cobalt_service import cobalt

logger = logging.getLogger(__name__)


class InstagramDownloader(BaseDownloader):
    """Instagram downloader using Cobalt API - simple and reliable"""
    
    def __init__(self):
        super().__init__()

    def _extract_shortcode(self, url: str) -> Optional[str]:
        """Extract shortcode from Instagram URL"""
        patterns = [
            r'instagram\.com/p/([A-Za-z0-9_-]+)',
            r'instagram\.com/reel/([A-Za-z0-9_-]+)',
            r'instagram\.com/reels/([A-Za-z0-9_-]+)',
            r'instagram\.com/tv/([A-Za-z0-9_-]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def platform_id(self) -> str:
        return 'instagram'

    def can_handle(self, url: str) -> bool:
        return any(x in url for x in ["instagram.com", "instagr.am"])

    async def get_formats(self, url: str) -> List[Dict]:
        """Get available formats"""
        self.update_progress('status_getting_info', 0)
        
        try:
            result = await cobalt.request(url)
            
            if result.success:
                self.update_progress('status_getting_info', 100)
                return [{'id': 'best', 'quality': 'Best', 'ext': 'mp4'}]
            else:
                raise DownloadError(f"Ошибка: {result.error}")
                
        except DownloadError:
            raise
        except Exception as e:
            logger.error(f"[Instagram] Error: {e}")
            raise DownloadError(f"Ошибка: {str(e)}")

    async def download(self, url: str, format_id: Optional[str] = None) -> Tuple[str, Path]:
        """Download video using Cobalt API"""
        shortcode = self._extract_shortcode(url) or 'video'
        logger.info(f"[Instagram] Downloading: {shortcode}")
        
        download_dir = Path(__file__).parent.parent.parent / "downloads"
        
        filename, file_path = await cobalt.download(
            url, 
            download_dir,
            progress_callback=self.update_progress
        )
        
        if not file_path:
            raise DownloadError("Не удалось загрузить видео")
        
        metadata = f"Instagram\n<a href=\"{url}\">Ссылка</a>"
        return metadata, file_path
