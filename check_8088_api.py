#!/usr/bin/env python3
import requests

paths = [
    '/docs',
    '/openapi.json',
    '/v1/chat/completions',
    '/api/v1/chat',
    '/chat',
    '/api/chat',
]

for path in paths:
    url = f'http://localhost:8088{path}'
    try:
        print(f'Testing {url}...')
        resp = requests.get(url, timeout=5)
        print(f'  Status: {resp.status_code}')
        if resp.status_code == 200:
            ct = resp.headers.get('content-type', 'unknown')
            print(f'  Content-Type: {ct}')
            print(f'  Preview: {resp.text[:200]}')
    except Exception as e:
        print(f'  Error: {e}')
    print()
