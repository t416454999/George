#!/usr/bin/env python3
"""极光引擎 · GitHub AI工具排行采集
新增：GitHub Trending 每周趋势发现 + Star 变化追踪
输出: GitHub工具排行.json（含 stable + trending 两个板块）
"""
import json, os, time, re
from datetime import datetime

OUTPUT = os.path.join(os.getcwd(), 'GitHub工具排行.json')
HISTORY = os.path.join(os.getcwd(), '.github_tools_history.json')

# 核心仓库（稳定追踪）
CORE_REPOS = [
    ('Ollama', 'ollama/ollama',
     '本地大模型运行工具，一键下载并运行 Llama、DeepSeek、Qwen 等开源模型。'),
    ('LangChain', 'langchain-ai/langchain',
     'LLM 应用开发框架，提供链式调用、Agent 编排、RAG 检索增强生成等核心能力。'),
    ('Vercel AI SDK', 'vercel/ai',
     'Vercel 推出的 AI SDK，提供统一的 LLM 调用接口，支持流式输出、多模型切换。'),
    ('AutoGen', 'microsoft/autogen',
     '微软开源的多 Agent 对话框架，支持多个 AI Agent 协同完成复杂任务。'),
    ('DeepSeek-V3', 'deepseek-ai/DeepSeek-V3',
     '深度求索开源大语言模型，MoE 架构 671B 参数，性能对标 GPT-4。'),
    ('Stable Diffusion', 'CompVis/stable-diffusion',
     '开源文生图模型，支持文本到图像生成，生态最丰富的图像生成框架。'),
    ('Cursor', 'getcursor/cursor',
     'AI 原生代码编辑器，深度集成 Claude 和 GPT 模型，支持自然语言编程和多文件重构。'),
]

# AI 相关关键词（筛选 trending repos）
AI_KEYWORDS = [
    'ai', 'llm', 'gpt', 'claude', 'llama', 'deepseek', 'chatgpt',
    'agent', 'machine-learning', 'deep-learning', 'language-model',
    'transformer', 'rag', 'embedding', 'vector', 'neural',
    'openai', 'anthropic', 'huggingface', 'diffusion',
    'copilot', 'chatbot', 'multimodal', 'vision', 'nlp',
    'mlops', 'prompt', 'fine-tune', 'generative', 'llmops',
]


def load_history():
    if os.path.exists(HISTORY):
        try:
            with open(HISTORY) as f:
                return json.load(f)
        except:
            pass
    return {}


def save_history(data):
    with open(HISTORY, 'w') as f:
        json.dump(data, f)


def fetch_stars(repo_path):
    """通过 GitHub API 获取仓库信息"""
    url = f'https://api.github.com/repos/{repo_path}'
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Aurora-Engine/1.0',
            'Accept': 'application/vnd.github.v3+json',
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return {
                'stars': data.get('stargazers_count', 0),
                'forks': data.get('forks_count', 0),
                'description': data.get('description', ''),
                'language': data.get('language', ''),
                'topics': data.get('topics', []),
            }
    except Exception as e:
        print(f'  [API] {repo_path}: {type(e).__name__}')
        return None


def scrape_trending(since='weekly'):
    """爬 GitHub Trending 页面，返回 AI 相关项目"""
    trending = []
    try:
        from bs4 import BeautifulSoup
        import urllib.request

        url = f'https://github.com/trending?since={since}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        })
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read()

        soup = BeautifulSoup(html, 'html.parser')
        articles = soup.select('article.Box-row')

        for art in articles[:30]:
            h2 = art.select_one('h2 a')
            if not h2:
                continue
            repo_full = h2.get('href', '').strip('/')
            desc_el = art.select_one('p')
            desc = desc_el.get_text(strip=True) if desc_el else ''

            # 过滤：只保留 AI 相关
            text_lower = (repo_full + ' ' + desc).lower()
            if not any(k in text_lower for k in AI_KEYWORDS):
                continue

            # 本周新增 star
            stars_el = art.select_one('.d-inline-block.float-sm-right')
            stars_period = 0
            if stars_el:
                t = stars_el.get_text(strip=True).replace(',', '').replace(' ', '')
                m = re.search(r'([\d.]+)(k)?', t)
                if m:
                    val = float(m.group(1))
                    stars_period = int(val * 1000) if m.group(2) else int(val)

            # 用 API 补全详细数据
            info = fetch_stars(repo_full)
            time.sleep(0.5)
            if info and info['stars'] > 50:
                name = repo_full.split('/')[-1]
                trending.append({
                    '名称': name,
                    'repo': repo_full,
                    '说明': desc or info['description'],
                    '星标': info['stars'],
                    '本周新增': stars_period,
                    '语言': info.get('language', '') or '',
                })

    except ImportError:
        print('  [Trending] BeautifulSoup 未安装，跳过趋势采集')
    except Exception as e:
        print(f'  [Trending] 异常: {type(e).__name__}')

    return trending


def fmt_stars(n):
    if n is None:
        return '?'
    if n >= 1000:
        return f'{n / 1000:.1f}k'
    return str(n)


def main():
    now = datetime.now()
    print(f'[{now.strftime("%H:%M:%S")}] GitHub 工具排行采集开始')

    history = load_history()

    # ── 1. 核心仓库 ──
    results = []
    print('\n── 核心仓库 ──')
    for name, repo, desc in CORE_REPOS:
        info = fetch_stars(repo)
        if info:
            stars = info['stars']
            prev = history.get(repo, {}).get('stars', stars)
            change = stars - prev
        else:
            prev = history.get(repo, {}).get('stars', 0)
            stars = prev
            change = 0

        change_str = f'+{change}' if change > 0 else ('─' if change == 0 else str(change))
        results.append({
            '名称': name,
            'repo': repo,
            '说明': desc,
            '星标': fmt_stars(stars),
            '本周变化': change_str,
            '语言': (info.get('language', '') or '') if info else '',
        })
        print(f'  {name}: {fmt_stars(stars)} ({change_str})')
        time.sleep(0.5)

        if info:
            history[repo] = {'stars': stars, 'updated': now.isoformat()}

    # ── 2. 本周趋势 ──
    print('\n── GitHub Trending（本周） ──')
    core_set = {r[1] for r in CORE_REPOS}
    trending = [t for t in scrape_trending('weekly') if t['repo'] not in core_set]

    for t in trending[:12]:
        if t['本周新增'] >= 1000:
            extra = f'+{t["本周新增"] / 1000:.1f}k / {t["本周新增"]}'
        else:
            extra = f'+{t["本周新增"]}' if t['本周新增'] else 'new'
        print(f'  {t["名称"]}: {fmt_stars(t["星标"])} ({extra})')

    # ── 3. 输出 ──
    output = {
        'updated': now.strftime('%Y-%m-%dT%H:%M:%S+08:00'),
        'stable': results,
        'trending': trending[:12],
    }

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n  写入完成: {len(results)} 核心 + {len(trending[:12])} 趋势')

    # 如果旧格式（平铺数组）还存在，兼容性删除
    save_history(history)


if __name__ == '__main__':
    main()
