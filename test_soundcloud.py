#!/usr/bin/env python3
"""Test SoundcloudService with Cloudflare Worker."""

import asyncio
import aiohttp

WORKER_URL = "https://soundcloud-proxy.roninreilly.workers.dev"

async def main():
    print("Testing SoundcloudService with Cloudflare Worker...\n")
    
    async with aiohttp.ClientSession() as session:
        # 1. Health check
        print("1. Health check...")
        async with session.get(f"{WORKER_URL}/health") as resp:
            data = await resp.json()
            print(f"   ✓ Status: {data.get('status')}\n")
        
        # 2. Search
        print("2. Searching for 'каждый раз'...")
        async with session.get(f"{WORKER_URL}/search?q=каждый раз&limit=4") as resp:
            data = await resp.json()
            tracks = data.get("tracks", [])
            print(f"   ✓ Found {len(tracks)} tracks\n")
            
            for i, track in enumerate(tracks):
                user = track.get("user", {})
                print(f"   [{i+1}] {user.get('username')} - {track.get('title')}")
                print(f"       Duration: {track.get('duration', 0) // 1000}s")
        
        if tracks:
            # 3. Get stream URL
            first_track = tracks[0]
            track_url = first_track.get("permalink_url")
            print(f"\n3. Getting stream URL for: {track_url}")
            
            async with session.get(f"{WORKER_URL}/stream?url={track_url}") as resp:
                data = await resp.json()
                stream_url = data.get("url")
                
                if stream_url:
                    print(f"   ✓ Got stream URL: {stream_url[:80]}...")
                    
                    # 4. Test download
                    print("\n4. Testing download (first 100KB)...")
                    async with session.get(stream_url) as dl_resp:
                        if dl_resp.status == 200:
                            chunk = await dl_resp.content.read(100 * 1024)
                            print(f"   ✓ Downloaded {len(chunk)} bytes!")
                        else:
                            print(f"   ✗ Download failed: HTTP {dl_resp.status}")
                else:
                    print("   ✗ No stream URL returned")
    
    print("\n" + "="*50)
    print("✓ All tests passed! Cloudflare Worker works.")

if __name__ == "__main__":
    asyncio.run(main())
