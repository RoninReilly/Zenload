#!/usr/bin/env python3
"""Test the new SoundcloudService using yt-dlp - standalone version."""

import asyncio
import json
import subprocess
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import aiohttp


class SoundcloudService:
    """SoundCloud service using yt-dlp for search and stream URLs."""

    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=2)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _run_ytdlp(self, args: List[str], timeout: int = 30) -> Optional[str]:
        cmd = ["yt-dlp", "--no-warnings"] + args
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0:
                return result.stdout
            print(f"yt-dlp error: {result.stderr[:200]}")
        except Exception as e:
            print(f"yt-dlp exception: {e}")
        return None

    def _parse_track(self, data: Dict[str, Any]) -> Dict[str, Any]:
        formats = data.get("formats", [])
        stream_url = None
        
        for fmt in formats:
            if fmt.get("protocol") == "http" and fmt.get("acodec") != "none":
                stream_url = fmt.get("url")
                break
        
        if not stream_url:
            for fmt in formats:
                if fmt.get("acodec") != "none":
                    stream_url = fmt.get("url")
                    break

        duration_ms = int((data.get("duration") or 0) * 1000)

        return {
            "id": data.get("id"),
            "title": data.get("title") or "SoundCloud Track",
            "permalink_url": data.get("webpage_url") or data.get("url"),
            "duration": duration_ms,
            "user": {
                "username": data.get("uploader"),
                "full_name": data.get("uploader"),
            },
            "_stream_url": stream_url,
        }

    async def search_tracks(self, query: str, limit: int = 4) -> List[Dict[str, Any]]:
        if not query:
            return []

        loop = asyncio.get_event_loop()

        def _search():
            args = ["--dump-json", "--flat-playlist", f"scsearch{limit}:{query}"]
            output = self._run_ytdlp(args, timeout=15)
            if not output:
                return []

            tracks = []
            for line in output.strip().split('\n'):
                if line:
                    try:
                        data = json.loads(line)
                        track_url = data.get("url") or data.get("webpage_url")
                        if track_url:
                            tracks.append({
                                "id": data.get("id"),
                                "title": data.get("title") or "SoundCloud Track",
                                "permalink_url": track_url,
                                "duration": int((data.get("duration") or 0) * 1000),
                                "user": {"username": data.get("uploader")},
                                "_stream_url": None,
                                "_url": track_url,
                            })
                    except json.JSONDecodeError:
                        continue
            return tracks

        return await asyncio.wait_for(
            loop.run_in_executor(self._executor, _search),
            timeout=20
        )

    async def resolve_track(self, url: str) -> Optional[Dict[str, Any]]:
        loop = asyncio.get_event_loop()

        def _resolve():
            args = ["--dump-json", "--no-download", url]
            output = self._run_ytdlp(args, timeout=20)
            if not output:
                return None
            try:
                return self._parse_track(json.loads(output))
            except json.JSONDecodeError:
                return None

        return await asyncio.wait_for(
            loop.run_in_executor(self._executor, _resolve),
            timeout=25
        )

    async def get_stream_url(self, track: Dict[str, Any]) -> Optional[str]:
        stream_url = track.get("_stream_url")
        if stream_url:
            return stream_url

        track_url = track.get("_url") or track.get("permalink_url")
        if not track_url:
            return None

        full_track = await self.resolve_track(track_url)
        if full_track:
            return full_track.get("_stream_url")
        return None

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


async def main():
    print("Testing SoundcloudService (yt-dlp based)...\n")
    
    service = SoundcloudService()
    
    print("1. Searching for 'каждый раз'...")
    try:
        tracks = await service.search_tracks("каждый раз", limit=4)
        print(f"   ✓ Found {len(tracks)} tracks\n")
        
        if not tracks:
            print("   ✗ No tracks found!")
            return 1
            
        print("2. Track info:")
        for i, track in enumerate(tracks):
            title = track.get("title", "Unknown")
            user = track.get("user", {})
            artist = user.get("username") or "Unknown"
            duration_s = track.get("duration", 0) // 1000
            print(f"   [{i+1}] {artist} - {title} ({duration_s}s)")
        
        print(f"\n3. Getting stream URL for first track...")
        first_track = tracks[0]
        stream_url = await service.get_stream_url(first_track)
        
        if stream_url:
            print(f"   ✓ Got stream URL: {stream_url[:80]}...")
        else:
            print("   ✗ Failed to get stream URL")
            return 1
            
        print("\n4. Testing download (first 100KB)...")
        session = await service._get_session()
        async with session.get(stream_url) as resp:
            if resp.status == 200:
                chunk = await resp.content.read(100 * 1024)
                print(f"   ✓ Downloaded {len(chunk)} bytes successfully!")
            else:
                print(f"   ✗ Download failed: HTTP {resp.status}")
                return 1
                
    except Exception as e:
        print(f"   ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        await service.close()
        
    print("\n" + "="*50)
    print("✓ All tests passed! SoundcloudService works.")
    return 0

if __name__ == "__main__":
    exit(asyncio.run(main()))
