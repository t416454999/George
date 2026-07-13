#!/usr/bin/env python3
"""极光引擎 · 选题库 API 生成
每天 08:00 / 14:00 / 20:00 聚合所有热点数据，供选题库调用。
"""
import json, os, re
from datetime import datetime, timezone, timedelta

BASE = '/var/www/boke'
OUTPUT = os.path.join(BASE, '选题库API.json')
TZ = timezone(timedelta(hours=8))

FILES = {
    '平台热点': 'platform-hot.json',
    'HackerNews': 'hn-translated.json',
    '行业热议': 'industry-buzz.json',
    '金融热点_国内': '金融API.json',
    '金融热点_国外': '金融API-国外.json',
    'GitHub工具排行': 'GitHub工具排行.json',
    '文章数据库': '文章数据库.json',
}

def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return {'error': str(e)}

def main():
    now = datetime.now(TZ)
    result = {
        '更新时间': now.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        '数据源': {},
    }

    for key, filename in FILES.items():
        path = os.path.join(BASE, filename)
        data = load_json(path)
        result['数据源'][key] = data

    # 摘要统计
    stats = {'数据源数量': len(FILES)}
    for key, filename in FILES.items():
        data = load_json(os.path.join(BASE, filename))
        if isinstance(data, dict):
            if 'articles' in data:
                stats[key] = len(data['articles'])
            elif 'platforms' in data:
                total = sum(len(v) for v in data['platforms'].values())
                stats[key] = f"{total}条 / {len(data['platforms'])}平台"
            elif data.get('stable') or data.get('trending'):
                stats[key] = f"{len(data.get('stable',[]))}核心 + {len(data.get('trending',[]))}趋势"
            else:
                stats[key] = 'unknown'
        elif isinstance(data, list):
            stats[key] = len(data)
        else:
            stats[key] = 'unknown'

    result['统计'] = stats
    result['说明'] = '选题库聚合API，每天 08:00 / 14:00 / 20:00 更新。各数据源更新节奏不同，以各源自身时间为准。'

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[选题库] {result['更新时间']} 已生成，共 {len(FILES)} 个数据源")
    return 0

if __name__ == '__main__':
    exit(main())
