import asyncio
import httpx

async def check_entities():
    async with httpx.AsyncClient(timeout=10) as client:
        # 检查实体
        resp = await client.get('http://localhost:8080/api/v1/entities/novel/7')
        entities = resp.json()
        print('Total entities:', entities.get('total', 0))
        for e in entities.get('items', [])[:10]:
            print(f"  - {e.get('canonical_name')} ({e.get('entity_type')})")
        
        # 检查关系
        resp2 = await client.get('http://localhost:8080/api/v1/entities/novel/7/relationships')
        rels = resp2.json()
        print('Relationships:', rels.get('total', 0))

asyncio.run(check_entities())
