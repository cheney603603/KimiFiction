import asyncio
import httpx
import time

async def write_chapter(chapter_num):
    async with httpx.AsyncClient(timeout=300) as client:
        print(f'=== 开始写第{chapter_num}章 ===')
        
        resp = await client.post('http://localhost:8080/api/v1/workflow/chapter/7', json={
            'novel_id': 7,
            'chapter_number': chapter_num
        })
        
        print(f'Status: {resp.status_code}')
        data = resp.json()
        print(f'Response: {data}')
        
        if resp.status_code == 200 and data.get('task_id'):
            task_id = data['task_id']
            print(f'任务ID: {task_id}')
            
            # 轮询等待完成
            for i in range(60):
                await asyncio.sleep(10)
                
                try:
                    resp2 = await client.get(f'http://localhost:8080/api/v1/tasks/{task_id}')
                    task_data = resp2.json()
                    status = task_data.get('status')
                    print(f'  [{i+1}] Status: {status}')
                    
                    if status in ['completed', 'failed']:
                        print(f'  任务完成: {task_data}')
                        break
                except Exception as e:
                    print(f'  检查任务出错: {e}')
        
        # 检查实体
        await asyncio.sleep(5)
        resp3 = await client.get('http://localhost:8080/api/v1/entities/novel/7')
        entities = resp3.json()
        print(f'当前实体数: {entities.get("total", 0)}')

async def main():
    for ch in range(2, 6):
        await write_chapter(ch)
        print()

asyncio.run(main())
