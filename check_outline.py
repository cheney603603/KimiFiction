#!/usr/bin/env python3
"""检查章节细纲状态"""
import requests
import json

BASE_URL = "http://localhost:8080/api/v1"
NOVEL_ID = 1

def check_workflow_progress():
    resp = requests.get(f"{BASE_URL}/workflow/progress/{NOVEL_ID}", timeout=10)
    print(f"Workflow Progress: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    return resp.json() if resp.status_code == 200 else None

def check_outline_detail():
    resp = requests.get(f"{BASE_URL}/workflow/phase-result/{NOVEL_ID}/outline_detail", timeout=10)
    print(f"\nOutline Detail: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(json.dumps(data, indent=2, ensure_ascii=False)[:2000])
        return data
    return None

def check_chapters():
    resp = requests.get(f"{BASE_URL}/chapters/novel/{NOVEL_ID}", timeout=10)
    print(f"\nChapters: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Total chapters: {data.get('total', 0)}")
        for ch in data.get('items', [])[:5]:
            print(f"  - Chapter {ch.get('chapter_number')}: {ch.get('title')} ({ch.get('word_count', 0)} words)")
    return resp.json() if resp.status_code == 200 else None

if __name__ == "__main__":
    print("="*60)
    print("Checking Workflow State")
    print("="*60)
    
    progress = check_workflow_progress()
    outline = check_outline_detail()
    chapters = check_chapters()
    
    if outline and outline.get("data"):
        print("\n[OK] Outline data exists")
        if isinstance(outline["data"], dict) and "chapter_outlines" in outline["data"]:
            outlines = outline["data"]["chapter_outlines"]
            print(f"Found {len(outlines)} chapter outlines")
            for o in outlines[:3]:
                print(f"  - Chapter {o.get('chapter_number')}: {o.get('title', 'Untitled')}")
    else:
        print("\n[ERROR] No outline detail data found")
        print("Please complete the 'outline_detail' phase first")
