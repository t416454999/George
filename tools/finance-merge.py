#!/usr/bin/env python3
"""极光引擎 · 国内外数据合并脚本
阿里云服务器 cron 每 5 分钟执行一次：
1. git fetch + reset 同步最新数据（不再用 git pull，避免文件冲突）
2. 合并国外数据到国内 金融API.json
3. 去重 + 排序 + 写入
"""
import json, os, subprocess
from datetime import datetime

DOMESTIC_FILE = '/var/www/boke/金融API.json'
FOREIGN_FILE = '/var/www/boke/金融API-国外.json'
BUZZ_FILE = '/var/www/boke/industry-buzz.json'
HN_FILE = '/var/www/boke/hn-translated.json'
REPO_DIR = '/var/www/boke'

def git_sync():
    """用 fetch + reset --hard 替代 git pull，避免因本地修改导致的冲突"""
    try:
        subprocess.run(['git', 'fetch', 'origin'], cwd=REPO_DIR, capture_output=True, timeout=30)
        subprocess.run(['git', 'reset', '--hard', 'origin/main'], cwd=REPO_DIR, capture_output=True, timeout=30)
        print(f'  git sync: OK')
    except Exception as e:
        print(f'  git sync: {e}')

def merge():
    """合并国内外数据"""
    domestic = []
    if os.path.exists(DOMESTIC_FILE):
        try:
            with open(DOMESTIC_FILE, 'r', encoding='utf-8') as f:
                domestic = json.load(f).get('articles', [])
        except:
            pass

    foreign = []
    if os.path.exists(FOREIGN_FILE):
        try:
            with open(FOREIGN_FILE, 'r', encoding='utf-8') as f:
                foreign = json.load(f).get('articles', [])
        except:
            pass

    merge_buzz()

    domestic_ids = {a['id'] for a in domestic}
    new_count = 0
    for a in foreign:
        if a['id'] not in domestic_ids:
            domestic.insert(0, a)
            domestic_ids.add(a['id'])
            new_count += 1

    # 优先排中文来源：同等日期下国内源在前
    chinese_sources = {'华尔街见闻','新浪财经','第一财经','财联社','金十数据','东方财富','每经网'}
    domestic.sort(key=lambda x: (x.get('日期', '') or '', 0 if x.get('来源','') not in chinese_sources else 1))
    domestic = list(reversed(domestic))[:50]

    output = {
        'updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'source': '极光引擎 · 金融热点API',
        'description': '国内+国外金融热点实时聚合，每15分钟自动更新',
        'count': len(domestic),
        'articles': domestic
    }

    with open(DOMESTIC_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f'  合并完成: 国外新增 {new_count}, 总 {len(domestic)}')

def merge_buzz():
    """合并 hn-translated.json -> 行业热议API.json"""
    buzz = []
    hn = []
    if os.path.exists(BUZZ_FILE):
        try:
            with open(BUZZ_FILE, 'r', encoding='utf-8') as f:
                buzz = json.load(f).get('articles', [])
        except: pass
    if os.path.exists(HN_FILE):
        try:
            with open(HN_FILE, 'r', encoding='utf-8') as f:
                hn = json.load(f).get('articles', [])
        except: pass
    if not hn:
        print('  [buzz] 无HN翻译数据')
        return
    ids = {a['id'] for a in buzz}
    added = 0
    for a in hn:
        if a['id'] not in ids:
            buzz.insert(0, a); ids.add(a['id']); added += 1
    buzz.sort(key=lambda x: x.get('日期',''), reverse=True)
    buzz = buzz[:50]
    out = {
        'updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'source': '极光引擎 · 行业热议API',
        'description': '行业动态/商业八卦/消费维权实时聚合',
        'count': len(buzz),
        'articles': buzz
    }
    with open(BUZZ_FILE, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'  [buzz] HN翻译合并: +{added}, 总 {len(buzz)}')

if __name__ == '__main__':
    git_sync()
    merge()
