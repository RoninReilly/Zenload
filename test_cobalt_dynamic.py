import asyncio
import logging
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO)

# Ensure we can import from src
sys.path.insert(0, os.getcwd())

from src.utils.cobalt_service import cobalt

async def test():
    print('=== Testing Cobalt Service Dynamic Instances ===')
    
    # Force fetch instances
    print("Fetching instances...")
    instances = await cobalt._get_instances()
    print(f'Fetched {len(instances)} instances')
    
    if not instances:
        print('❌ No instances fetched!')
        return

    print('Top 3 instances:')
    for inst in instances[:3]:
        print(f' - {inst}')

    # Test request
    print('\nTesting request with first instance...')
    url = 'https://www.instagram.com/reel/DRZHg84jN1Z/'
    result = await cobalt.request(url)
    
    if result.success:
        print(f'✅ Request successful!')
        print(f'   URL: {result.url[:60]}...')
        if result.filename:
            print(f'   Filename: {result.filename}')
    else:
        print(f'❌ Request failed: {result.error}')

if __name__ == "__main__":
    asyncio.run(test())
