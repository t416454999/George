#!/usr/bin/env python3
"""极光引擎 · GitHub AI工具排行采集
获取 AI/开发者工具的 GitHub star 数，生成排行榜 JSON。
输出: 当前工作目录下的 GitHub工具排行.json
"""
import json, os, time
from datetime import datetime

OUTPUT = os.path.join(os.getcwd(), 'GitHub工具排行.json')

REPOS = [
    ('Cursor', 'cursor/cursor', 'AI 原生代码编辑器，基于 VS Code 深度集成 Claude 和 GPT 模型，支持自然语言编程和多文件重构。'),
    ('Ollama', 'ollama/ollama', '本地大模型运行工具，一键下载并运行 Llama、DeepSeek、Qwen 等开源模型。支持 CPU 和 GPU 推理。'),
    ('LangChain', 'langchain-ai/langchain', 'LLM 应用开发框架，提供链式调用、Agent 编排、RAG 检索增强生成等核心能力。'),
    ('Vercel AI SDK', 'vercel/ai', 'Vercel 推出的 AI SDK（原 v0 团队维护），提供统一的 LLM 调用接口，支持流式输出、多模型切换。'),
    ('AutoGen', 'microsoft/autogen', '微软开源的多 Agent 对话框架，支持多个 AI Agent 协同完成复杂任务，适用于企业级自动化流程。'),
    ('DeepSeek-V3', 'deepseek-ai/DeepSeek-V3', '深度求索开源大语言模型，MoE 架构 671B 参数，性能对标 GPT-4，支持 128K 上下文。'),
    ('Stable Diffusion', 'CompVis/stable-diffusion', '开源文生图模型，Stability AI 维护，支持文本到图像生成，生态最丰富的图像生成框架。'),
]

def fetch_stars(repo_path):
    """通过 GitHub API 获取 star 数"""
    url = f'https://api.github.com/repos/{repo_path}'
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Aurora-Engine/1.0',
            'Accept': 'application/vnd.github.v3+json',
        })
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
            return data.get('stargazers_count', 0)
    except Exception as e:
        print(f'  {repo_path}: {type(e).__name__}')
        return None

def fmt_stars(n):
    if n is None: return '?'
    if n >= 1000: return f'{n/1000:.0f}k'
    return str(n)

def main():
    print(f'[{datetime.now().strftime("%H:%M:%S")}] GitHub 工具排行采集开始')
    results = []
    for name, repo, desc in REPOS:
        stars = fetch_stars(repo)
        label = fmt_stars(stars)
        results.append({
            '名称': name,
            '链接': f'https://github.com/{repo}',
            '说明': desc,
            '星标': f'{label} stars' if stars else '? stars',
            '排行变化': '─',
        })
        print(f'  {name}: {label} stars')
        time.sleep(0.5)

    results.sort(key=lambda x: int((x['星标'].split('k')[0].replace('?','0').replace(',','')) if 'k' in x['星标'] else '0'), reverse=True)

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'  写入完成, 共 {len(results)} 个工具')

if __name__ == '__main__':
    main()
