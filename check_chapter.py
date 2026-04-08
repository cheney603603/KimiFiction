#!/usr/bin/env python3
import requests

print('=== Chapter 1 Content ===')
resp = requests.get('http://localhost:8080/api/v1/chapters/novel/1', timeout=10)
chapters = resp.json()
print(f"Total chapters: {chapters.get('total', 0)}")
for ch in chapters.get('items', []):
    print(f"Chapter {ch.get('chapter_number')}: {ch.get('title')} ({ch.get('word_count', 0)} words)")
    if ch.get('chapter_number') == 1:
        detail = requests.get(f"http://localhost:8080/api/v1/chapters/{ch.get('id')}", timeout=10)
        data = detail.json()
        content = data.get('content', '')
        print(f"\nContent preview (first 800 chars):")
        print(content[:800])
        print('...')
