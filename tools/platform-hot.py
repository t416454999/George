#!/usr/bin/env python3
"""极光引擎 · 平台热点聚合
采集各平台公开热点榜单（仅聚合公开的标题/排名/热度，链接回原平台）。
可在 GitHub Actions 或阿里云服务器运行。
输出: 当前工作目录下的 platform-hot.json
"""
import json, requests, re, os, html as html_mod
from datetime import datetime

OUTPUT = os.path.join(os.getcwd(), 'platform-hot.json')
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def fmt_heat(n):
    if not n: return ''
    n = int(n)
    if n >= 100000000: return f'{n/100000000:.1f}亿'
    if n >= 10000: return f'{n/10000:.1f}万'
    return str(n)

def fetch_weibo():
    items = []
    try:
        headers = {**HEADERS, "Referer": "https://weibo.com/"}
        r = requests.get('https://weibo.com/ajax/side/hotSearch', headers=headers, timeout=10)
        data = r.json()
        for item in data.get('real_time', []):
            word = (item.get('word') or '').strip()
            if not word: continue
            raw = item.get('raw_hot', 0) or 0
            items.append({
                'rank': item.get('rank', 0) or (len(items) + 1),
                'title': word,
                'heat': fmt_heat(raw),
                'raw_heat': raw,
                'link': f'https://s.weibo.com/weibo?q={requests.utils.quote(word)}',
            })
        print(f'  微博热搜: {len(items)} 条')
    except Exception as e:
        print(f'  微博热搜: {type(e).__name__}')
    return items

def fetch_zhihu():
    items = []
    try:
        headers = {**HEADERS, "Referer": "https://www.zhihu.com/"}
        r = requests.get('https://www.zhihu.com/billboard', headers=headers, timeout=10)
        m = re.search(r'<script id="js-initialData"[^>]*>(.*?)</script>', r.text, re.DOTALL)
        if m:
            decoded = html_mod.unescape(m.group(1))
            payload = json.loads(decoded)
            def find_hot(obj, depth=0):
                if depth > 8: return None
                if isinstance(obj, dict):
                    for k in ['hotList', 'list', 'data']:
                        val = obj.get(k, [])
                        if isinstance(val, list) and len(val) > 0:
                            if any(isinstance(x, dict) and ('title' in x or 'Title' in x) for x in val[:3]):
                                return val
                    for v in obj.values():
                        r = find_hot(v, depth + 1)
                        if r: return r
                return None
            hot_list = find_hot(payload)
            if hot_list:
                for i, item in enumerate(hot_list[:50]):
                    title = None
                    target = item.get('target', item)
                    for key in ['title', 'Title', 'question']:
                        t = target.get(key, '')
                        if isinstance(t, dict): t = t.get('title', '')
                        if t: title = t; break
                    if not title: continue
                    heat = item.get('heat', item.get('hotScore', target.get('voteup_count', 0))) or 0
                    qid = ''
                    link = target.get('url', target.get('link', ''))
                    if not link:
                        qid = target.get('id', '')
                        if qid: link = f'https://www.zhihu.com/question/{qid}'
                    items.append({
                        'rank': i + 1,
                        'title': re.sub(r'<[^>]+>', '', str(title)).strip(),
                        'heat': fmt_heat(heat) if isinstance(heat, (int, float)) else str(heat),
                        'raw_heat': int(heat) if isinstance(heat, (int, float)) else 0,
                        'link': link,
                    })
        print(f'  知乎热榜: {len(items)} 条')
    except Exception as e:
        print(f'  知乎热榜: {type(e).__name__}')
    return items

def fetch_bilibili():
    items = []
    try:
        r = requests.get('https://api.bilibili.com/x/web-interface/popular', headers=HEADERS, timeout=10)
        data = r.json()
        for i, v in enumerate(data.get('data', {}).get('list', [])):
            title = (v.get('title') or '').strip()
            if not title: continue
            view = v.get('stat', {}).get('view', 0) or 0
            items.append({
                'rank': i + 1,
                'title': re.sub(r'<[^>]+>', '', title),
                'heat': fmt_heat(view),
                'raw_heat': view,
                'link': f'https://www.bilibili.com/video/{v.get("bvid", "")}',
            })
        print(f'  B站热门: {len(items)} 条')
    except Exception as e:
        print(f'  B站热门: {type(e).__name__}')
    return items

def fetch_baidu():
    items = []
    try:
        headers = {**HEADERS, "Referer": "https://top.baidu.com/"}
        r = requests.get('https://top.baidu.com/api/board?platform=wise&tab=realtime', headers=headers, timeout=10)
        data = r.json()
        for card in data.get('data', {}).get('cards', []):
            for item in card.get('content', []):
                title = (item.get('word') or item.get('query') or '').strip()
                if not title: continue
                hot = item.get('hotScore', 0) or 0
                url = item.get('url', '') or ''
                if url and not url.startswith('http'):
                    url = 'https://top.baidu.com' + url
                items.append({
                    'rank': item.get('index', len(items) + 1),
                    'title': title,
                    'heat': fmt_heat(hot),
                    'raw_heat': hot,
                    'link': url or f'https://www.baidu.com/s?wd={requests.utils.quote(title)}',
                })
        print(f'  百度热搜: {len(items)} 条')
    except Exception as e:
        print(f'  百度热搜: {type(e).__name__}')
    return items

def fetch_douyin():
    items = []
    try:
        headers = {**HEADERS, "Referer": "https://www.douyin.com/"}
        r = requests.get('https://www.douyin.com/hot/', headers=headers, timeout=10)
        m = re.search(r'<script id="RENDER_DATA" type="application/json">(.*?)</script>', r.text, re.DOTALL)
        if m:
            raw = m.group(1)
            try:
                decoded = html_mod.unescape(raw); payload = json.loads(decoded)
            except:
                try: payload = json.loads(raw)
                except: payload = None
            if payload:
                def find_hot_list(obj, depth=0):
                    if depth > 10: return None
                    if isinstance(obj, dict):
                        if any(k in obj for k in ['hot_list', 'word_list']):
                            for k in ['hot_list', 'word_list']:
                                val = obj.get(k, [])
                                if isinstance(val, list) and len(val) > 0: return val
                        for v in obj.values():
                            r = find_hot_list(v, depth + 1)
                            if r: return r
                    if isinstance(obj, list):
                        for v in obj:
                            r = find_hot_list(v, depth + 1)
                            if r: return r
                    return None
                hot_list = find_hot_list(payload)
                if hot_list:
                    for i, item in enumerate(hot_list[:50]):
                        title = None
                        for key in ['word', 'title', 'hot_title', 'content']:
                            title = item.get(key, '')
                            if title: break
                        if not title: continue
                        heat = item.get('hot_value', item.get('heat', item.get('hot', 0))) or 0
                        items.append({
                            'rank': i + 1, 'title': str(title).strip(),
                            'heat': fmt_heat(heat), 'raw_heat': heat,
                            'link': 'https://www.douyin.com/hot/',
                        })
        print(f'  抖音热榜: {len(items)} 条')
    except Exception as e:
        print(f'  抖音热榜: {type(e).__name__}')
    return items

def fetch_toutiao():
    items = []
    try:
        headers = {**HEADERS, "Referer": "https://www.toutiao.com/"}
        urls = ['https://www.toutiao.com/hot/', 'https://www.toutiao.com/api/pc/hot/', 'https://www.toutiao.com/trending/']
        for url in urls:
            if items: break
            r = requests.get(url, headers=headers, timeout=10)
            try:
                data = r.json()
                for path in [('data',), ('data', 'list'), ('hot_list',)]:
                    lst = data
                    for p in path:
                        lst = lst.get(p, {}) if isinstance(lst, dict) else lst
                    if isinstance(lst, list) and len(lst) > 0:
                        for i, item in enumerate(lst[:50]):
                            title = item.get('title', item.get('Title', item.get('word', '')))
                            if not title: continue
                            heat = item.get('hot_value', item.get('heat', item.get('HotValue', 0))) or 0
                            link = item.get('url', item.get('link', item.get('Url', '')))
                            if link and not link.startswith('http'):
                                link = 'https://www.toutiao.com' + link
                            items.append({
                                'rank': i + 1, 'title': str(title).strip(),
                                'heat': fmt_heat(heat), 'raw_heat': heat,
                                'link': link or 'https://www.toutiao.com/',
                            })
            except:
                m = re.search(r'<script[^>]*>window\.\_INITIAL_STATE\_\s*=\s*({.*?});', r.text, re.DOTALL)
                if m:
                    try:
                        state = json.loads(m.group(1))
                        for key in ['hotList', 'list', 'data']:
                            lst = state.get(key, state.get('hot', {}).get(key, []))
                            if isinstance(lst, list) and len(lst) > 0:
                                for i, item in enumerate(lst[:50]):
                                    title = item.get('title', item.get('Title', ''))
                                    if not title: continue
                                    heat = item.get('hot_value', item.get('heat', 0)) or 0
                                    items.append({
                                        'rank': i + 1, 'title': str(title).strip(),
                                        'heat': fmt_heat(heat), 'raw_heat': heat,
                                        'link': item.get('url', item.get('Url', '')),
                                    })
                                if items: break
                    except: pass
        print(f'  头条热榜: {len(items)} 条' if items else '  头条热榜: 0 条')
    except Exception as e:
        print(f'  头条热榜: {type(e).__name__}')
    return items

def fetch_xiaohongshu():
    items = []
    try:
        r = requests.get('https://60s.viki.moe/v2/rednote', headers=HEADERS, timeout=10)
        data = r.json()
        for item in data.get('data', []):
            title = (item.get('title') or '').strip()
            if not title: continue
            items.append({
                'rank': item.get('rank', len(items) + 1),
                'title': title,
                'heat': item.get('score', '') or '',
                'raw_heat': 0,
                'link': item.get('link', '') or f'https://www.xiaohongshu.com/search_result?keyword={requests.utils.quote(title)}',
            })
        print(f'  小红书热榜: {len(items)} 条')
    except Exception as e:
        print(f'  小红书热榜: {type(e).__name__}')
    return items

def fetch_kuaishou():
    items = []
    try:
        headers = {**HEADERS, "Referer": "https://www.kuaishou.com/"}
        r = requests.get('https://www.kuaishou.com/?isHome=1', headers=headers, timeout=10)
        m = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\});', r.text, re.DOTALL)
        if not m:
            m = re.search(r'<script>window\.__INITIAL_STATE__\s*=\s*({.*?})</script>', r.text, re.DOTALL)
        if m:
            raw = html_mod.unescape(m.group(1)); payload = json.loads(raw)
            def find_hot(obj, depth=0):
                if depth > 6: return None
                if isinstance(obj, dict):
                    for k in ['hotList', 'list', 'data', 'feeds', 'hotWords']:
                        val = obj.get(k, [])
                        if isinstance(val, list) and len(val) > 5:
                            if any(isinstance(x, dict) and ('name' in x or 'title' in x or 'caption' in x) for x in val[:3]): return val
                    for v in obj.values():
                        r = find_hot(v, depth + 1)
                        if r: return r
                if isinstance(obj, list):
                    for v in obj:
                        r = find_hot(v, depth + 1)
                        if r: return r
                return None
            hot_list = find_hot(payload)
            if hot_list:
                for i, item in enumerate(hot_list[:50]):
                    title = None
                    for key in ['name', 'title', 'caption', 'word', 'description']:
                        t = item.get(key, '')
                        if t: title = t; break
                    if not title: continue
                    url = item.get('url', item.get('link', item.get('shareUrl', '')))
                    if url and not url.startswith('http'): url = 'https://www.kuaishou.com' + url
                    items.append({
                        'rank': i + 1, 'title': str(title).strip(),
                        'heat': '', 'raw_heat': 0,
                        'link': url or 'https://www.kuaishou.com/',
                    })
        print(f'  快手热榜: {len(items)} 条')
    except Exception as e:
        print(f'  快手热榜: {type(e).__name__}')
    return items

def main():
    print(f'[{datetime.now().strftime("%H:%M:%S")}] 平台热点采集开始')
    platforms = {
        '微博热搜': fetch_weibo(), '知乎热榜': fetch_zhihu(), 'B站热门': fetch_bilibili(),
        '百度热搜': fetch_baidu(), '抖音热榜': fetch_douyin(), '头条热榜': fetch_toutiao(),
        '小红书热榜': fetch_xiaohongshu(), '快手热榜': fetch_kuaishou(),
    }
    output = {
        'updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'source': '极光引擎 · 平台热点聚合',
        'description': '各平台实时热点榜单聚合（仅公开标题+链接，不缓存全文）',
        'count': sum(len(v) for v in platforms.values()),
        'platforms': platforms,
    }
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    total = sum(len(v) for v in platforms.values())
    stats = ' | '.join(f'{k}:{len(v)}' for k, v in platforms.items() if v)
    print(f'  写入完成, 共 {total} 条')
    print(f'  {stats}')

if __name__ == '__main__':
    main()
