from typing import Optional, Type, List
from .base import BaseDownloader, DownloadError
from .instagram import InstagramDownloader
from .tiktok import TikTokDownloader
from .yandex import YandexMusicDownloader
from .pinterest import PinterestDownloader
from .youtube import YouTubeDownloader
from .soundcloud import SoundcloudDownloader


class DownloaderFactory:
    """Factory class to manage and create appropriate downloaders"""
    
    _downloaders: List[Type[BaseDownloader]] = [
        InstagramDownloader,
        TikTokDownloader,
        YandexMusicDownloader,
        PinterestDownloader,
        YouTubeDownloader,
        SoundcloudDownloader
    ]

    @classmethod
    def get_downloader(cls, url: str) -> Optional[BaseDownloader]:
        """Get appropriate downloader for the given URL"""
        for downloader_class in cls._downloaders:
            downloader = downloader_class()
            if downloader.can_handle(url):
                return downloader
        return None


__all__ = ['DownloaderFactory', 'DownloadError']
