#!/usr/bin/env python3
"""极光引擎 · 境外金融热点采集
由 GitHub Actions 触发，从海外金融源抓取数据。
输出: 金融API-国外.json（推送回 GitHub，阿里云自动拉取合并）
"""
import json, hashlib, re, os, time
from datetime import datetime

OUTPUT = '金融API-国外.json'
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/130.0.0.0"}

def clean(text):
    return re.sub(r'<[^>]+>', '', (text or '')).strip()

def make_id(title, source):
    return hashlib.md5((title + source).encode()).hexdigest()[:8]

def fetch_yahoo_finance():
    """Yahoo Finance RSS (top stories + business)"""
    articles = []
    rss_urls = [
        'https://finance.yahoo.com/news/rssindex',
        'https://finance.yahoo.com/rss/topstories',
    ]
    import feedparser
    for url in rss_urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = clean(entry.get('title', ''))
                if not title or len(title) < 8: continue
                summary = clean(entry.get('summary', ''))[:200]
                articles.append({
                    'id': make_id(title, 'Yahoo Finance'),
                    '标题': title,
                    '摘要': summary,
                    '来源': 'Yahoo Finance',
                    '日期': datetime.now().strftime('%Y-%m-%d'),
                    '热度': 65,
                    '链接': entry.get('link', ''),
                    '标签': []
                })
        except:
            pass
    print(f'  Yahoo Finance: {len(articles)}')
    return articles

def fetch_reuters():
    """Reuters RSS"""
    articles = []
    urls = [
        'https://www.reutersagency.com/feed/',
        'https://news.google.com/rss/search?q=site:reuters.com+financial&hl=en-US',
    ]
    import feedparser
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = clean(entry.get('title', ''))
                if not title or len(title) < 8: continue
                summary = clean(entry.get('summary', ''))[:200]
                articles.append({
                    'id': make_id(title, 'Reuters'),
                    '标题': title,
                    '摘要': summary,
                    '来源': 'Reuters',
                    '日期': datetime.now().strftime('%Y-%m-%d'),
                    '热度': 68,
                    '链接': entry.get('link', ''),
                    '标签': []
                })
        except:
            pass
    print(f'  Reuters: {len(articles)}')
    return articles

def fetch_cnbc():
    """CNBC RSS"""
    articles = []
    urls = [
        'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114',
        'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664',
    ]
    import feedparser
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                title = clean(entry.get('title', ''))
                if not title or len(title) < 8: continue
                summary = clean(entry.get('summary', ''))[:200]
                articles.append({
                    'id': make_id(title, 'CNBC'),
                    '标题': title,
                    '摘要': summary,
                    '来源': 'CNBC',
                    '日期': datetime.now().strftime('%Y-%m-%d'),
                    '热度': 66,
                    '链接': entry.get('link', ''),
                    '标签': []
                })
        except:
            pass
    print(f'  CNBC: {len(articles)}')
    return articles

def fetch_marketwatch():
    """MarketWatch RSS"""
    articles = []
    try:
        import feedparser
        feed = feedparser.parse('https://feeds.marketwatch.com/marketwatch/topstories/')
        for entry in feed.entries[:5]:
            title = clean(entry.get('title', ''))
            if not title or len(title) < 8: continue
            summary = clean(entry.get('summary', ''))[:200]
            articles.append({
                'id': make_id(title, 'MarketWatch'),
                '标题': title,
                '摘要': summary,
                '来源': 'MarketWatch',
                '日期': datetime.now().strftime('%Y-%m-%d'),
                '热度': 62,
                '链接': entry.get('link', ''),
                '标签': []
            })
    except:
        pass
    print(f'  MarketWatch: {len(articles)}')
    return articles

def merge():
    all_articles = []
    all_articles += fetch_yahoo_finance()
    all_articles += fetch_reuters()
    all_articles += fetch_cnbc()
    all_articles += fetch_marketwatch()

    # 加载已有的国外数据
    existing = []
    if os.path.exists(OUTPUT):
        try:
            with open(OUTPUT, 'r', encoding='utf-8') as f:
                existing = json.load(f).get('articles', [])
        except:
            pass

    existing_ids = {a['id'] for a in existing}
    for a in all_articles:
        if a['id'] not in existing_ids:
            existing.insert(0, a)
            existing_ids.add(a['id'])

    existing.sort(key=lambda x: x.get('日期', ''), reverse=True)
    today = datetime.now().strftime('%Y-%m-%d')
    today_items = [a for a in existing if a.get('日期') == today]
    recent = [a for a in existing if a not in today_items and a.get('日期', '')[:7] == today[:7]]
    older = [a for a in existing if a not in today_items and a not in recent]
    existing = today_items[:10] + recent[:15] + older[:25]
    existing = existing[:50]

    output = {
        'updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'source': '极光引擎 · 金融热点API (Global)',
        'count': len(existing),
        'articles': existing
    }

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'总条数: {len(existing)}, 新增: {len(all_articles)}')

if __name__ == '__main__':
    merge()
