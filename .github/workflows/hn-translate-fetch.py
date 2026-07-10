#!/usr/bin/env python3
"""极光引擎 · HN 热点采集 + Google 翻译
由 GitHub Actions（美国服务器）触发，畅通访问 Google Translate。
输出: hn-translated.json（推送回 GitHub，阿里云拉取合并）
"""
import json, requests, hashlib, os, re
from datetime import datetime

OUTPUT = 'hn-translated.json'
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130.0.0.0"}

def clean(text):
    return re.sub(r'<[^>]+>', '', (text or '')).strip()

def make_id(title):
    return hashlib.md5(title.encode()).hexdigest()[:8]

def translate(text):
    """Google Translate — GitHub Actions 美国服务器畅通"""
    if not text or len(text) < 8: return text
    try:
        url = 'https://translate.googleapis.com/translate_a/single'
        params = {'client': 'gtx', 'sl': 'en', 'tl': 'zh-CN', 'dt': 't', 'q': text[:1000]}
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            parts = r.json()
            result = ''.join(parts[0][i][0] for i in range(len(parts[0])))
            return result.strip() or text
    except:
        pass
    return text

def fetch():
    """Hacker News top stories → 翻译"""
    articles = []
    try:
        r = requests.get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
        ids = r.json()[:20]
        for sid in ids:
            try:
                r2 = requests.get(f'https://hacker-news.firebaseio.com/v0/item/{sid}.json', timeout=10)
                item = r2.json()
                en = item.get('title', '')
                if not en or len(en) < 8: continue
                cn = translate(en)
                url = item.get('url', f'https://news.ycombinator.com/item?id={sid}')
                articles.append({
                    'id': make_id(en),
                    '标题': cn,
                    '原文': en,
                    '摘要': en,
                    '来源': 'Hacker News',
                    '日期': datetime.now().strftime('%Y-%m-%d'),
                    '热度': 65, '分类': '科技商业',
                    '链接': url, '标签': []
                })
            except:
                pass
    except:
        pass
    print(f'HN: {len(articles)} 篇')
    return articles

def merge(articles):
    existing = []
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, 'r', encoding='utf-8') as f:
                existing = json.load(f).get('articles', [])
        except:
            pass
    ids = {a['id'] for a in existing}
    for a in articles:
        if a['id'] not in ids:
            existing.insert(0, a); ids.add(a['id'])
    existing.sort(key=lambda x: x.get('日期',''), reverse=True)
    existing = existing[:50]
    out = {
        'updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'source': '极光引擎 · HN翻译',
        'count': len(existing),
        'articles': existing
    }
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'写入: {len(existing)} 条')

if __name__ == '__main__':
    merge(fetch())
