import asyncio
import httpx
from core.config import settings

async def test_apis():
    print("--- Testing GDELT ---")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get('https://api.gdeltproject.org/api/v2/doc/doc?query=peru&mode=artlist&format=json')
            print(f"Status Code: {r.status_code}")
            if r.status_code == 200:
                print("GDELT OK! Fetching data...")
                data = r.json()
                print(f"Articles fetched: {len(data.get('articles', []))}")
            else:
                print(f"Error Message: {r.text[:100]}")
    except Exception as e:
        print(f"GDELT Exception: {e}")

    print("\n--- Testing X (Twitter) ---")
    try:
        headers = {"Authorization": f"Bearer {settings.X_API_BEARER_TOKEN}"}
        params = {"query": "peru", "max_results": 10, "tweet.fields": "created_at"}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get('https://api.twitter.com/2/tweets/search/recent', headers=headers, params=params)
            print(f"Status Code: {r.status_code}")
            if r.status_code == 200:
                print("X OK! Fetching data...")
                data = r.json()
                print(f"Tweets fetched: {len(data.get('data', []))}")
            else:
                print(f"Error Message: {r.text}")
    except Exception as e:
        print(f"X Exception: {e}")

if __name__ == '__main__':
    asyncio.run(test_apis())
