import os
import re
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import requests
import yt_dlp
from urllib.parse import urlparse
from .base import BaseDownloader, DownloadError

logger = logging.getLogger(__name__)

class RateLimitError(DownloadError):
    """Custom exception for rate limit errors"""
    pass

class InstagramDownloader(BaseDownloader):
    def __init__(self):
        super().__init__()
        self.last_request_time = 0
        self.min_request_interval = 2  # Minimum seconds between requests
        self.max_retries = 3

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

    async def _make_request(self, url: str, retry_count: int = 0) -> requests.Response:
        """Make a rate-limited request with retry logic"""
        if retry_count >= self.max_retries:
            raise RateLimitError("Превышен лимит запросов к Instagram. Пожалуйста, подождите несколько минут и попробуйте снова.")

        # Implement rate limiting
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            await asyncio.sleep(self.min_request_interval - time_since_last)

        self.last_request_time = asyncio.get_event_loop().time()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        response = await asyncio.to_thread(requests.get, url, headers=headers, allow_redirects=False, timeout=15)
        
        if response.status_code == 429:
            wait_time = (2 ** retry_count) * 5
            logger.warning(f"[Instagram] Rate limited, waiting {wait_time} seconds before retry")
            await asyncio.sleep(wait_time)
            return await self._make_request(url, retry_count + 1)

        if response.status_code in [301, 302, 303, 307, 308]:
            redirect_url = response.headers.get('location', '')
            if redirect_url:
                if redirect_url.startswith('/'):
                    parsed = urlparse(url)
                    redirect_url = f"{parsed.scheme}://{parsed.netloc}{redirect_url}"
                logger.info(f"[Instagram] Following redirect: {url} -> {redirect_url}")
                return await self._make_request(redirect_url, retry_count)
        
        return response

    def platform_id(self) -> str:
        return 'instagram'

    def can_handle(self, url: str) -> bool:
        return any(x in url for x in ["instagram.com", "instagr.am", "/share/"])

    def _get_ydl_opts(self, format_id: Optional[str] = None) -> Dict:
        """Get yt-dlp options (no cookies!)"""
        return {
            'format': format_id if format_id else 'best',
            'nooverwrites': True,
            'no_color': True,
            'no_warnings': True,
            'quiet': False,
            'progress_hooks': [self._progress_hook],
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'en-US,en;q=0.9'
            }
        }

    async def _try_embed_download(self, url: str) -> Optional[Dict]:
        """Try downloading using Instagram embed page (no auth required for public posts)"""
        shortcode = self._extract_shortcode(url)
        if not shortcode:
            logger.info("[Instagram] Could not extract shortcode for embed")
            return None

        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/"
        logger.info(f"[Instagram] Trying embed URL: {embed_url}")

        try:
            response = await self._make_request(embed_url)
            if response.status_code != 200:
                logger.info(f"[Instagram] Embed request failed with status {response.status_code}")
                return None

            html = response.text

            # Pattern 1: video_url in JSON
            video_match = re.search(r'"video_url"\s*:\s*"([^"]+)"', html)
            if video_match:
                video_url = video_match.group(1).replace('\\u0026', '&').replace('\\/', '/')
                logger.info("[Instagram] Found video_url in embed JSON")
                return {'video_url': video_url, 'shortcode': shortcode, 'source': 'embed'}

            # Pattern 2: og:video meta tag
            og_video = re.search(r'<meta[^>]+property="og:video"[^>]+content="([^"]+)"', html)
            if og_video:
                video_url = og_video.group(1).replace('&amp;', '&')
                logger.info("[Instagram] Found og:video in embed")
                return {'video_url': video_url, 'shortcode': shortcode, 'source': 'embed'}

            # Pattern 3: video tag src
            video_src = re.search(r'<video[^>]+src="([^"]+)"', html)
            if video_src:
                video_url = video_src.group(1).replace('&amp;', '&')
                logger.info("[Instagram] Found video src in embed")
                return {'video_url': video_url, 'shortcode': shortcode, 'source': 'embed'}

            # Pattern 4: additionalDataLoaded JSON
            config_match = re.search(r'window\.__additionalDataLoaded\s*\(\s*[\'"][^\'"]+[\'"]\s*,\s*(\{.+?\})\s*\)\s*;', html, re.DOTALL)
            if config_match:
                try:
                    data = json.loads(config_match.group(1))
                    if 'shortcode_media' in data:
                        media = data['shortcode_media']
                        if media.get('is_video') and media.get('video_url'):
                            logger.info("[Instagram] Found video in additionalDataLoaded")
                            return {'video_url': media['video_url'], 'shortcode': shortcode, 'source': 'embed', 'info': media}
                except json.JSONDecodeError:
                    pass

            logger.info("[Instagram] No video found in embed page")
            return None

        except Exception as e:
            logger.info(f"[Instagram] Embed approach failed: {e}")
            return None

    async def _try_external_service(self, url: str) -> Optional[Dict]:
        """Try downloading using external service (FastDL)"""
        shortcode = self._extract_shortcode(url)
        if not shortcode:
            return None

        logger.info("[Instagram] Trying external service (FastDL)")
        
        # FastDL
        try:
            fastdl_url = "https://fastdl.app/api/convert"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
                'Origin': 'https://fastdl.app',
                'Referer': 'https://fastdl.app/'
            }
            
            post_url = url if url.startswith('http') else f"https://www.instagram.com/p/{shortcode}/"
            data = {'url': post_url}
            
            response = await asyncio.to_thread(requests.post, fastdl_url, headers=headers, data=data, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('url'):
                    logger.info("[Instagram] Got video URL from FastDL")
                    return {'video_url': result['url'], 'shortcode': shortcode, 'source': 'fastdl', 'title': result.get('title', '')}
                elif result.get('video'):
                    logger.info("[Instagram] Got video from FastDL response")
                    return {'video_url': result['video'], 'shortcode': shortcode, 'source': 'fastdl'}
        except Exception as e:
            logger.info(f"[Instagram] FastDL failed: {e}")

        # indown.io
        try:
            logger.info("[Instagram] Trying indown.io")
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
            
            session = requests.Session()
            page_response = await asyncio.to_thread(session.get, "https://indown.io/", headers=headers, timeout=10)
            
            token_match = re.search(r'name="_token"[^>]+value="([^"]+)"', page_response.text)
            if token_match:
                token = token_match.group(1)
                post_data = {'_token': token, 'link': url}
                
                response = await asyncio.to_thread(session.post, "https://indown.io/download", headers=headers, data=post_data, timeout=15)
                
                if response.status_code == 200:
                    video_match = re.search(r'href="([^"]+)"[^>]*class="[^"]*download[^"]*"', response.text)
                    if video_match:
                        video_url = video_match.group(1)
                        if 'instagram' in video_url or 'cdninstagram' in video_url:
                            logger.info("[Instagram] Got video URL from indown.io")
                            return {'video_url': video_url, 'shortcode': shortcode, 'source': 'indown'}
        except Exception as e:
            logger.info(f"[Instagram] indown.io failed: {e}")

        return None

    async def _resolve_share_url(self, url: str) -> str:
        """Resolve Instagram share URL to actual post URL"""
        if '/share/' not in url:
            return url

        logger.info(f"[Instagram] Processing share URL: {url}")
        try:
            self.update_progress('status_getting_info', 10)
            response = await self._make_request(url)
            if response.status_code != 200:
                raise DownloadError(f"Ошибка HTTP {response.status_code}")
            
            final_url = str(response.url)
            if '?' in final_url:
                final_url = final_url.split('?')[0]
            final_url = final_url.rstrip('/')
            logger.info(f"[Instagram] Resolved to: {final_url}")
            self.update_progress('status_getting_info', 20)
            return final_url

        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"[Instagram] Share URL resolution failed: {e}")
            if "429" in str(e):
                raise DownloadError("Превышен лимит запросов к Instagram.")
            raise DownloadError(f"Ошибка при обработке share-ссылки: {str(e)}")

    async def get_formats(self, url: str) -> List[Dict]:
        """Get available formats for URL"""
        try:
            self.update_progress('status_getting_info', 0)
            resolved_url = await self._resolve_share_url(url)
            logger.info(f"[Instagram] Getting formats for: {resolved_url}")

            self.update_progress('status_getting_info', 30)
            
            # Try embed first
            embed_result = await self._try_embed_download(resolved_url)
            if embed_result and embed_result.get('video_url'):
                return [{'id': 'best', 'quality': 'Best', 'ext': 'mp4'}]

            # Try external service
            external_result = await self._try_external_service(resolved_url)
            if external_result and external_result.get('video_url'):
                return [{'id': 'best', 'quality': 'Best', 'ext': 'mp4'}]

            # Try yt-dlp
            download_dir = Path(__file__).parent.parent.parent / "downloads"
            download_dir.mkdir(exist_ok=True)
            
            try:
                ydl_opts = self._get_ydl_opts()
                ydl_opts['outtmpl'] = str(download_dir / '%(id)s.%(ext)s')
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = await asyncio.to_thread(ydl.extract_info, str(resolved_url), download=False)
                    if info and 'formats' in info:
                        formats = []
                        seen = set()
                        for f in info['formats']:
                            if not f.get('height'):
                                continue
                            quality = f"{f['height']}p"
                            if quality not in seen:
                                formats.append({'id': f['format_id'], 'quality': quality, 'ext': f['ext']})
                                seen.add(quality)
                        if formats:
                            logger.info("[Instagram] Got formats using yt-dlp")
                            return sorted(formats, key=lambda x: int(x['quality'][:-1]), reverse=True)
            except Exception as e:
                logger.info(f"[Instagram] yt-dlp format extraction failed: {e}")

            raise DownloadError("Не удалось получить информацию о медиафайле")
                
        except RateLimitError:
            raise
        except Exception as e:
            logger.error(f"[Instagram] Format extraction failed: {e}")
            if "429" in str(e):
                raise DownloadError("Превышен лимит запросов к Instagram.")
            raise DownloadError(f"Ошибка при получении форматов: {str(e)}")

    async def download(self, url: str, format_id: Optional[str] = None) -> Tuple[str, Path]:
        """Download video from URL using fallback chain: embed -> external service -> yt-dlp"""
        try:
            self.update_progress('status_downloading', 0)
            resolved_url = await self._resolve_share_url(url)
            logger.info(f"[Instagram] Downloading from: {resolved_url}")

            download_dir = Path(__file__).parent.parent.parent / "downloads"
            download_dir.mkdir(exist_ok=True)
            download_dir = download_dir.resolve()
            logger.info(f"[Instagram] Download directory: {download_dir}")
            
            shortcode = self._extract_shortcode(resolved_url) or 'video'
            
            # === Method 1: Embed endpoint ===
            self.update_progress('status_downloading', 10)
            embed_result = await self._try_embed_download(resolved_url)
            if embed_result and embed_result.get('video_url'):
                logger.info("[Instagram] Downloading via embed method")
                try:
                    response = await asyncio.to_thread(
                        requests.get, embed_result['video_url'], 
                        headers={'User-Agent': 'Mozilla/5.0'}, 
                        timeout=60
                    )
                    if response.status_code == 200:
                        file_path = download_dir / f"{shortcode}.mp4"
                        with open(file_path, 'wb') as f:
                            f.write(response.content)
                        logger.info("[Instagram] Downloaded successfully via embed")
                        self.update_progress('status_downloading', 100)
                        return self._prepare_metadata_simple(shortcode, resolved_url), file_path
                except Exception as e:
                    logger.info(f"[Instagram] Embed download failed: {e}")

            # === Method 2: External service ===
            self.update_progress('status_downloading', 30)
            external_result = await self._try_external_service(resolved_url)
            if external_result and external_result.get('video_url'):
                logger.info("[Instagram] Downloading via external service")
                try:
                    response = await asyncio.to_thread(
                        requests.get, external_result['video_url'],
                        headers={'User-Agent': 'Mozilla/5.0'},
                        timeout=60
                    )
                    if response.status_code == 200:
                        file_path = download_dir / f"{shortcode}.mp4"
                        with open(file_path, 'wb') as f:
                            f.write(response.content)
                        logger.info("[Instagram] Downloaded successfully via external service")
                        self.update_progress('status_downloading', 100)
                        return self._prepare_metadata_simple(shortcode, resolved_url, external_result.get('title')), file_path
                except Exception as e:
                    logger.info(f"[Instagram] External service download failed: {e}")

            # === Method 3: yt-dlp ===
            self.update_progress('status_downloading', 50)
            try:
                ydl_opts = self._get_ydl_opts(format_id)
                ydl_opts['outtmpl'] = str(download_dir / '%(id)s.%(ext)s')
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    self.update_progress('status_downloading', 60)
                    info = await asyncio.to_thread(ydl.extract_info, str(resolved_url), download=True)
                    if info:
                        filename = ydl.prepare_filename(info)
                        file_path = Path(filename).resolve()
                        if file_path.exists():
                            logger.info("[Instagram] Downloaded via yt-dlp")
                            return self._prepare_metadata(info, resolved_url), file_path
            except Exception as e:
                logger.info(f"[Instagram] yt-dlp download failed: {e}")

            raise DownloadError("Не удалось загрузить медиафайл. Все методы загрузки не сработали.")
                
        except RateLimitError:
            raise
        except DownloadError:
            raise
        except Exception as e:
            error_msg = str(e)
            if "Private video" in error_msg or "Private profile" in error_msg:
                raise DownloadError("Это приватный контент")
            elif "429" in error_msg:
                raise DownloadError("Превышен лимит запросов к Instagram.")
            else:
                logger.error(f"[Instagram] Download failed: {error_msg}")
                raise DownloadError(f"Ошибка загрузки: {error_msg}")

    def _prepare_metadata_simple(self, shortcode: str, url: str, title: str = None) -> str:
        if title:
            return f"Instagram\n{title}\n<a href=\"{url}\">Ссылка</a>"
        return f"Instagram\n<a href=\"{url}\">Ссылка</a>"

    def _prepare_metadata(self, info: Dict, url: str) -> str:
        def format_number(num):
            if not num:
                return "0"
            if num >= 1000000:
                return f"{num/1000000:.1f}M"
            if num >= 1000:
                return f"{num/1000:.1f}K"
            return str(num)

        likes = format_number(info.get('like_count', 0))
        username = info.get('user', {}).get('username', '') or info.get('uploader', '').replace('https://www.instagram.com/', '').strip()

        if info.get('view_count') or info.get('play_count'):
            views = format_number(info.get('view_count', 0) or info.get('play_count', 0))
            return f"Instagram | {views} | {likes}\nby <a href=\"{url}\">{username}</a>"
        else:
            return f"Instagram | {likes}\nby <a href=\"{url}\">{username}</a>"

    def _progress_hook(self, d: Dict[str, Any]):
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                if total > 0:
                    progress = int((downloaded / total) * 70) + 20
                    self.update_progress('status_downloading', progress)
            except Exception as e:
                logger.error(f"Error in progress hook: {e}")
