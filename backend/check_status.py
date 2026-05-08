import asyncio
import httpx

async def check():
    async with httpx.AsyncClient(timeout=10) as client:
        # 检查章节
        resp = await client.get('http://localhost:8080/api/v1/chapters/novel/7')
        chapters = resp.json()
        print(f"Chapters: {chapters.get('total', 0)}")
        for ch in chapters.get('items', [])[:5]:
            print(f"  Ch{ch['chapter_number']}: {ch.get('title', 'N/A')} ({ch.get('word_count', 0)}字)")
        
        # 检查实体
        resp2 = await client.get('http://localhost:8080/api/v1/entities/novel/7')
        entities = resp2.json()
        print(f"\nEntities: {entities.get('total', 0)}")

asyncio.run(check())
