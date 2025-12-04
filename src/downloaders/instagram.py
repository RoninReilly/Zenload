import os
import re
import json
import asyncio
import logging
import random
import string
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
    """Instagram downloader using Cobalt-style methods"""
    
    # Mobile API headers (like Cobalt)
    MOBILE_HEADERS = {
        "x-ig-app-locale": "en_US",
        "x-ig-device-locale": "en_US",
        "x-ig-mapped-locale": "en_US",
        "user-agent": "Instagram 275.0.0.27.98 Android (33/13; 280dpi; 720x1423; Xiaomi; Redmi 7; onclite; qcom; en_US; 458229237)",
        "accept-language": "en-US",
        "x-fb-http-engine": "Liger",
        "x-fb-client-ip": "True",
        "x-fb-server-cluster": "True",
        "content-length": "0",
    }
    
    # Common headers 
    COMMON_HEADERS = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "sec-gpc": "1",
        "sec-fetch-site": "same-origin",
        "x-ig-app-id": "936619743392459"
    }
    
    # Embed headers
    EMBED_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "max-age=0",
        "Dnt": "1",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }

    def __init__(self):
        super().__init__()
        self.last_request_time = 0
        self.min_request_interval = 1
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

    def platform_id(self) -> str:
        return 'instagram'

    def can_handle(self, url: str) -> bool:
        return any(x in url for x in ["instagram.com", "instagr.am", "/share/"])

    async def _get_media_id(self, shortcode: str) -> Optional[str]:
        """Get media_id from oEmbed API (like Cobalt)"""
        oembed_url = f"https://i.instagram.com/api/v1/oembed/?url=https://www.instagram.com/p/{shortcode}/"
        
        try:
            response = await asyncio.to_thread(
                requests.get, oembed_url, 
                headers=self.MOBILE_HEADERS, 
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                media_id = data.get('media_id')
                if media_id:
                    logger.info(f"[Instagram] Got media_id from oEmbed: {media_id}")
                    return media_id
        except Exception as e:
            logger.info(f"[Instagram] oEmbed failed: {e}")
        return None

    async def _request_mobile_api(self, media_id: str) -> Optional[Dict]:
        """Request Mobile API (like Cobalt) - main method"""
        api_url = f"https://i.instagram.com/api/v1/media/{media_id}/info/"
        
        try:
            response = await asyncio.to_thread(
                requests.get, api_url,
                headers=self.MOBILE_HEADERS,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                if items:
                    logger.info("[Instagram] Got data from Mobile API")
                    return items[0]
        except Exception as e:
            logger.info(f"[Instagram] Mobile API failed: {e}")
        return None

    async def _request_embed_captioned(self, shortcode: str) -> Optional[Dict]:
        """Request embed/captioned page and parse contextJSON (like Cobalt)"""
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        
        try:
            response = await asyncio.to_thread(
                requests.get, embed_url,
                headers=self.EMBED_HEADERS,
                timeout=15
            )
            if response.status_code != 200:
                return None
                
            html = response.text
            
            # Cobalt's pattern: "init",[],[(...)]]
            match = re.search(r'"init",\[\],\[(.*?)\]\],', html)
            if match:
                try:
                    embed_data = json.loads(match.group(1))
                    if embed_data and embed_data.get('contextJSON'):
                        context = json.loads(embed_data['contextJSON'])
                        logger.info("[Instagram] Got data from embed/captioned")
                        return {'gql_data': context}
                except:
                    pass
            
            # Fallback: look for video_url directly
            video_match = re.search(r'"video_url"\s*:\s*"([^"]+)"', html)
            if video_match:
                video_url = video_match.group(1).replace('\\u0026', '&').replace('\\/', '/')
                logger.info("[Instagram] Found video_url in embed")
                return {'video_url': video_url}
                
        except Exception as e:
            logger.info(f"[Instagram] Embed captioned failed: {e}")
        return None

    def _get_gql_params(self, html: str) -> Dict:
        """Extract GQL parameters from page HTML (like Cobalt)"""
        def get_object(name):
            match = re.search(rf'\["{name}",.*?,(\{{.*?\}}),\d+\]', html)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    pass
            return {}
        
        site_data = get_object('SiteData')
        polaris_data = get_object('PolarisSiteData')
        web_config = get_object('WebBloksVersioningID')
        push_info = get_object('InstagramWebPushInfo')
        lsd_data = get_object('LSD')
        security = get_object('InstagramSecurityConfig')
        
        lsd = lsd_data.get('token', ''.join(random.choices(string.ascii_letters + string.digits, k=12)))
        csrf = security.get('csrf_token', '')
        
        return {
            'headers': {
                'x-ig-app-id': web_config.get('appId', '936619743392459'),
                'X-FB-LSD': lsd,
                'X-CSRFToken': csrf,
                'x-asbd-id': '129477',
            },
            'body': {
                '__d': 'www',
                '__a': '1',
                '__user': '0',
                'lsd': lsd,
            }
        }

    async def _request_gql(self, shortcode: str) -> Optional[Dict]:
        """Request GraphQL API (like Cobalt)"""
        # First get the page to extract params
        page_url = f"https://www.instagram.com/p/{shortcode}/"
        
        try:
            response = await asyncio.to_thread(
                requests.get, page_url,
                headers=self.EMBED_HEADERS,
                timeout=15
            )
            if response.status_code != 200:
                return None
            
            params = self._get_gql_params(response.text)
            
            # Make GraphQL request
            gql_url = "https://www.instagram.com/graphql/query"
            headers = {
                **self.EMBED_HEADERS,
                **params['headers'],
                'content-type': 'application/x-www-form-urlencoded',
                'X-FB-Friendly-Name': 'PolarisPostActionLoadPostQueryQuery',
            }
            
            body = {
                **params['body'],
                'fb_api_caller_class': 'RelayModern',
                'fb_api_req_friendly_name': 'PolarisPostActionLoadPostQueryQuery',
                'variables': json.dumps({
                    'shortcode': shortcode,
                    'fetch_tagged_user_count': None,
                    'hoisted_comment_id': None,
                    'hoisted_reply_id': None
                }),
                'server_timestamps': 'true',
                'doc_id': '8845758582119845'  # Cobalt's doc_id
            }
            
            response = await asyncio.to_thread(
                requests.post, gql_url,
                headers=headers,
                data=body,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('data'):
                    logger.info("[Instagram] Got data from GraphQL")
                    return {'gql_data': data['data']}
                    
        except Exception as e:
            logger.info(f"[Instagram] GraphQL failed: {e}")
        return None

    def _extract_video_url(self, data: Dict) -> Optional[str]:
        """Extract video URL from API response"""
        # From video_url directly
        if data.get('video_url'):
            return data['video_url']
        
        # From Mobile API response
        if data.get('video_versions'):
            # Get highest quality
            best = max(data['video_versions'], key=lambda x: x.get('width', 0) * x.get('height', 0))
            return best.get('url')
        
        # From GQL response
        gql = data.get('gql_data', {})
        media = gql.get('shortcode_media') or gql.get('xdt_shortcode_media')
        if media:
            if media.get('video_url'):
                return media['video_url']
            if media.get('is_video') and media.get('video_url'):
                return media['video_url']
        
        return None

    async def _try_cobalt_methods(self, shortcode: str) -> Optional[Dict]:
        """Try all Cobalt-style methods in order"""
        
        # Method 1: Mobile API via oEmbed media_id
        media_id = await self._get_media_id(shortcode)
        if media_id:
            data = await self._request_mobile_api(media_id)
            if data:
                video_url = self._extract_video_url(data)
                if video_url:
                    return {'video_url': video_url, 'data': data, 'source': 'mobile_api'}
        
        # Method 2: Embed captioned
        data = await self._request_embed_captioned(shortcode)
        if data:
            video_url = self._extract_video_url(data)
            if video_url:
                return {'video_url': video_url, 'data': data, 'source': 'embed'}
        
        # Method 3: GraphQL
        data = await self._request_gql(shortcode)
        if data:
            video_url = self._extract_video_url(data)
            if video_url:
                return {'video_url': video_url, 'data': data, 'source': 'graphql'}
        
        return None

    async def _resolve_share_url(self, url: str) -> str:
        """Resolve Instagram share URL to actual post URL"""
        if '/share/' not in url:
            return url

        logger.info(f"[Instagram] Processing share URL: {url}")
        try:
            # Use curl user-agent (Cobalt's trick)
            response = await asyncio.to_thread(
                requests.get, url,
                headers={'User-Agent': 'curl/7.88.1'},
                allow_redirects=True,
                timeout=15
            )
            final_url = str(response.url)
            if '?' in final_url:
                final_url = final_url.split('?')[0]
            logger.info(f"[Instagram] Resolved to: {final_url}")
            return final_url
        except Exception as e:
            logger.error(f"[Instagram] Share URL resolution failed: {e}")
            raise DownloadError(f"Ошибка при обработке share-ссылки: {str(e)}")

    def _get_ydl_opts(self, format_id: Optional[str] = None) -> Dict:
        """Get yt-dlp options"""
        return {
            'format': format_id if format_id else 'best',
            'nooverwrites': True,
            'no_color': True,
            'no_warnings': True,
            'quiet': False,
            'progress_hooks': [self._progress_hook],
            'http_headers': self.COMMON_HEADERS
        }

    async def get_formats(self, url: str) -> List[Dict]:
        """Get available formats for URL"""
        try:
            self.update_progress('status_getting_info', 0)
            resolved_url = await self._resolve_share_url(url)
            shortcode = self._extract_shortcode(resolved_url)
            
            if not shortcode:
                raise DownloadError("Не удалось извлечь ID поста")
            
            logger.info(f"[Instagram] Getting formats for: {shortcode}")
            self.update_progress('status_getting_info', 30)
            
            # Try Cobalt methods first
            result = await self._try_cobalt_methods(shortcode)
            if result:
                return [{'id': 'best', 'quality': 'Best', 'ext': 'mp4'}]
            
            # Fall back to yt-dlp
            self.update_progress('status_getting_info', 60)
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
        except DownloadError:
            raise
        except Exception as e:
            logger.error(f"[Instagram] Format extraction failed: {e}")
            raise DownloadError(f"Ошибка при получении форматов: {str(e)}")

    async def download(self, url: str, format_id: Optional[str] = None) -> Tuple[str, Path]:
        """Download video from URL using Cobalt-style methods"""
        try:
            self.update_progress('status_downloading', 0)
            resolved_url = await self._resolve_share_url(url)
            shortcode = self._extract_shortcode(resolved_url)
            
            if not shortcode:
                raise DownloadError("Не удалось извлечь ID поста")

            logger.info(f"[Instagram] Downloading: {shortcode}")
            
            download_dir = Path(__file__).parent.parent.parent / "downloads"
            download_dir.mkdir(exist_ok=True)
            download_dir = download_dir.resolve()
            
            # === Method 1: Cobalt-style methods ===
            self.update_progress('status_downloading', 10)
            result = await self._try_cobalt_methods(shortcode)
            
            if result and result.get('video_url'):
                logger.info(f"[Instagram] Downloading via {result.get('source', 'unknown')} method")
                try:
                    response = await asyncio.to_thread(
                        requests.get, result['video_url'],
                        headers={'User-Agent': 'Mozilla/5.0'},
                        timeout=120
                    )
                    if response.status_code == 200:
                        file_path = download_dir / f"{shortcode}.mp4"
                        with open(file_path, 'wb') as f:
                            f.write(response.content)
                        logger.info(f"[Instagram] Downloaded successfully via {result.get('source')}")
                        self.update_progress('status_downloading', 100)
                        return self._prepare_metadata_simple(shortcode, resolved_url), file_path
                except Exception as e:
                    logger.info(f"[Instagram] Cobalt download failed: {e}")

            # === Method 2: yt-dlp fallback ===
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
