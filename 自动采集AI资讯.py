# -*- coding: utf-8 -*-
"""
============================================================
极光引擎 - 每日AI资讯自动采集脚本
功能：从国内AI媒体自动抓取最新资讯，更新文章数据库
运行：python 自动采集AI资讯.py
兼容：Python 3.8+，中国内地网络环境可直连
============================================================
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# 依赖检查与自动安装
# ============================================================
缺少的包 = []

try:
    import requests
except ImportError:
    缺少的包.append("requests")

try:
    import feedparser
except ImportError:
    缺少的包.append("feedparser")

try:
    from bs4 import BeautifulSoup
except ImportError:
    缺少的包.append("beautifulsoup4")

if 缺少的包:
    print(f"[极光引擎] 检测到缺少依赖包：{', '.join(缺少的包)}")
    print("[极光引擎] 正在自动安装...")
    import subprocess
    for 包名 in 缺少的包:
        subprocess.check_call([sys.executable, "-m", "pip", "install", 包名, "-q"])
    print("[极光引擎] 依赖安装完成，请重新运行脚本")
    # 重新导入
    import requests
    import feedparser
    from bs4 import BeautifulSoup


# ============================================================
# 配置区域
# ============================================================

# 数据文件路径
脚本目录 = Path(__file__).parent
数据库路径 = 脚本目录 / "文章数据库.json"
登记路径 = 脚本目录 / "修改登记.json"

# 当前采集智能体身份（运行前可通过环境变量覆盖）
采集智能体名称 = os.environ.get("AURORA_AGENT_NAME", "自动采集脚本 (Python)")
采集操作人 = os.environ.get("AURORA_OPERATOR", "GitHub Actions")

# HTTP 请求头（模拟浏览器，避免被反爬）
请求头 = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 请求超时（秒）
请求超时 = 20

# 每次采集最大文章数（每个来源）
每源最大文章数 = 10

# ============================================================
# 资讯来源配置
# ============================================================

原生资讯分类映射 = {
    "原生资讯": [
        "release", "launch", "introducing", "announce", "announcing", "new model",
        "research", "paper", "benchmark", "open source", "API", "developer",
        "safety", "alignment", "multimodal", "agent", "inference", "dataset",
        "发布", "推出", "研究", "论文", "模型", "开源"
    ],
}

资讯来源配置 = [
    {
        "名称": "OpenAI 官方",
        "RSS": "https://openai.com/news/rss.xml",
        "类型": "RSS",
        "固定分类": "原生资讯",
        "原生资讯": True,
        "分类映射": 原生资讯分类映射,
    },
    {
        "名称": "Hugging Face 官方",
        "RSS": "https://huggingface.co/blog/feed.xml",
        "类型": "RSS",
        "固定分类": "原生资讯",
        "原生资讯": True,
        "分类映射": 原生资讯分类映射,
    },
    {
        "名称": "Google DeepMind 官方",
        "RSS": "https://deepmind.google/blog/rss.xml",
        "类型": "RSS",
        "固定分类": "原生资讯",
        "原生资讯": True,
        "分类映射": 原生资讯分类映射,
    },
    {
        "名称": "arXiv AI",
        "RSS": "https://export.arxiv.org/rss/cs.AI",
        "类型": "RSS",
        "固定分类": "原生资讯",
        "原生资讯": True,
        "分类映射": 原生资讯分类映射,
    },
    {
        "名称": "机器之心",
        "RSS": "https://www.jiqizhixin.com/rss",
        "类型": "RSS",
        "分类映射": {
            "大模型": ["大模型", "GPT", "Claude", "Gemini", "LLM", "Llama", "DeepSeek", "Qwen", "通义",
                      "文心", "混元", "ChatGPT", "语言模型", "transformer"],
            "AI应用": ["应用", "产品", "落地", "Agent", "智能体", "Copilot", "助手", "搜索", "推荐",
                      "自动驾驶", "机器人", "医疗", "教育", "金融"],
            "AI绘画": ["绘画", "生成", "图像", "视频", "Sora", "Stable Diffusion", "Midjourney",
                      "DALL", "视觉", "图片", "视频生成", "StyleGAN"],
            "学术前沿": ["论文", "研究", "NeurIPS", "ICML", "CVPR", "ACL", "EMNLP", "ICLR",
                       "arXiv", "突破", "发现", "算法", "架构"],
            "行业动态": ["融资", "上市", "收购", "政策", "监管", "芯片", "算力", "GPU",
                       "市场", "报告", "趋势", "裁员", "招聘"],
            "开源工具": ["开源", "GitHub", "框架", "工具", "库", "SDK", "API", "HuggingFace",
                       "PyTorch", "TensorFlow", "代码", "编程"],
        },
    },
    {
        "名称": "量子位",
        "RSS": "https://www.qbitai.com/feed",
        "类型": "RSS",
        "分类映射": {
            "大模型": ["大模型", "GPT", "Claude", "Gemini", "LLM", "Llama", "DeepSeek", "通义千问",
                      "文心一言", "混元", "ChatGPT", "语言模型", "预训练"],
            "AI应用": ["应用", "产品", "落地", "Agent", "智能体", "Copilot", "助手", "搜索",
                      "推荐", "自动驾驶", "机器人", "医疗AI", "教育"],
            "AI绘画": ["绘画", "生成", "图像", "视频", "Sora", "Stable Diffusion", "Midjourney",
                      "DALL", "视觉", "图片", "视频生成"],
            "学术前沿": ["论文", "研究", "NeurIPS", "ICML", "CVPR", "ACL", "ICLR",
                       "arXiv", "突破", "发现", "算法"],
            "行业动态": ["融资", "上市", "收购", "政策", "监管", "芯片", "算力", "GPU",
                       "市场", "报告", "趋势"],
            "开源工具": ["开源", "GitHub", "框架", "工具", "库", "SDK", "API", "HuggingFace",
                       "PyTorch", "代码"],
        },
    },
    {
        "名称": "36氪",
        "RSS": "https://36kr.com/feed",
        "类型": "RSS",
        "分类映射": {
            "大模型": ["大模型", "GPT", "Claude", "Gemini", "LLM", "开源模型", "DeepSeek"],
            "AI应用": ["应用", "产品", "落地", "Agent", "智能体", "Copilot", "AI\\+", "机器人"],
            "AI绘画": ["绘画", "图像", "视频", "Sora", "Midjourney", "AI生成"],
            "学术前沿": ["论文", "研究", "突破", "发现", "算法"],
            "行业动态": ["融资", "上市", "收购", "政策", "芯片", "算力", "市场", "报告"],
            "开源工具": ["开源", "GitHub", "框架", "工具", "HuggingFace"],
        },
    },
    {
        "名称": "虎嗅",
        "RSS": "https://www.huxiu.com/rss/0.xml",
        "类型": "RSS",
        "分类映射": {
            "大模型": ["大模型", "GPT", "Claude", "Gemini", "LLM", "DeepSeek"],
            "AI应用": ["应用", "产品", "Agent", "智能体", "Copilot", "AI产品"],
            "AI绘画": ["绘画", "图像生成", "视频生成", "Sora", "Midjourney"],
            "学术前沿": ["论文", "研究", "突破", "算法"],
            "行业动态": ["融资", "上市", "收购", "政策", "芯片", "算力", "市场"],
            "开源工具": ["开源", "GitHub", "框架", "工具"],
        },
    },
    {
        "名称": "新浪科技",
        "RSS": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num=20",
        "类型": "API",
        "分类映射": {
            "大模型": ["大模型", "GPT", "Claude", "Gemini", "LLM", "DeepSeek"],
            "AI应用": ["应用", "产品", "Agent", "智能体", "AI产品", "机器人"],
            "AI绘画": ["绘画", "图像", "视频生成", "Sora", "Midjourney"],
            "学术前沿": ["论文", "研究", "突破", "算法"],
            "行业动态": ["融资", "上市", "收购", "政策", "芯片", "算力"],
            "开源工具": ["开源", "GitHub", "框架", "工具"],
        },
    },
    {
        "名称": "雷锋网",
        "RSS": "https://www.leiphone.com/feed",
        "类型": "RSS",
        "分类映射": {
            "大模型": ["大模型", "GPT", "Claude", "Gemini", "LLM", "DeepSeek"],
            "AI应用": ["应用", "产品", "Agent", "智能体", "AI产品", "机器人", "自动驾驶"],
            "AI绘画": ["绘画", "图像", "视频生成", "视觉"],
            "学术前沿": ["论文", "研究", "突破", "算法"],
            "行业动态": ["融资", "上市", "收购", "政策", "芯片", "算力", "安防"],
            "开源工具": ["开源", "GitHub", "框架", "工具"],
        },
    },
]

# ============================================================
# 金融资讯来源（独立配置，固定分类=金融）
# ============================================================

金融来源配置 = [
    {
        "名称": "华尔街见闻",
        "RSS": "https://wallstreetcn.com/feed",
        "类型": "RSS",
        "固定分类": "金融",
    },
    {
        "名称": "财联社",
        "RSS": "https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=8.4.6",
        "类型": "API",
        "固定分类": "金融",
    },
    {
        "名称": "金十数据",
        "RSS": "https://www.jin10.com/flash",
        "类型": "RSS",
        "固定分类": "金融",
    },
    {
        "名称": "东方财富",
        "RSS": "https://finance.eastmoney.com/rss/",
        "类型": "RSS",
        "固定分类": "金融",
    },
    {
        "名称": "新浪财经",
        "RSS": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2511&k=&num=20",
        "类型": "API",
        "固定分类": "金融",
    },
    {
        "名称": "第一财经",
        "RSS": "https://www.yicai.com/feed/",
        "类型": "RSS",
        "固定分类": "金融",
    },
    {
        "名称": "每经网",
        "RSS": "https://www.nbd.com.cn/rss/",
        "类型": "RSS",
        "固定分类": "金融",
    },
]

# ============================================================
# 金融API输出路径
# ============================================================

金融API路径 = 脚本目录 / "金融API.json"
金融API最大条数 = 50


# ============================================================
# 工具函数
# ============================================================

def 生成文章ID(标题, 来源):
    """根据标题和来源生成唯一ID"""
    文本 = f"{标题}_{来源}"
    hash_hex = hashlib.md5(文本.encode("utf-8")).hexdigest()
    # 取前8位十六进制转整数，保证在合理范围内
    return int(hash_hex[:8], 16)


def 自动分类(标题, 摘要, 来源配置):
    """根据关键词自动为文章分类"""
    标题摘要 = f"{标题} {摘要}".lower()
    分类映射 = 来源配置.get("分类映射", {})

    得分表 = {}
    for 分类, 关键词列表 in 分类映射.items():
        得分 = 0
        for 关键词 in 关键词列表:
            if 关键词.lower() in 标题摘要:
                得分 += 1
        得分表[分类] = 得分

    if 得分表:
        最高分分类 = max(得分表, key=得分表.get)
        if 得分表[最高分分类] > 0:
            return 最高分分类

    return "行业动态"  # 默认分类


def 计算热度(标题, 摘要):
    """简单热度计算（基于关键词热度权重）"""
    热词权重 = {
        "GPT-5": 10, "GPT": 8, "Claude": 8, "Gemini": 8, "Sora": 9,
        "DeepSeek": 9, "开源": 7, "发布": 6, "突破": 8, "革命": 7,
        "融资": 6, "上市": 7, "收购": 5, "AI Agent": 8, "机器人": 7,
        "芯片": 7, "Llama": 8, "Stable Diffusion": 7, "Midjourney": 7,
        "OpenAI": 9, "Google": 7, "微软": 7, "Meta": 7, "华为": 8,
        "视频生成": 8, "人形机器人": 8, "电影": 7, "医疗": 6,
    }
    文本 = f"{标题} {摘要}".lower()
    总分 = 0
    for 词, 权重 in 热词权重.items():
        if 词.lower() in 文本:
            总分 += 权重
    return min(总分 + 50, 99)  # 基础分50，上限99


def 清理文本(文本):
    """清理HTML标签和多余空白"""
    if not 文本:
        return ""
    # 移除HTML标签
    文本 = re.sub(r'<[^>]+>', '', 文本)
    # 移除多余空白
    文本 = re.sub(r'\s+', ' ', 文本)
    # 移除HTML实体
    文本 = 文本.replace('&nbsp;', ' ').replace('&amp;', '&')
    文本 = 文本.replace('&lt;', '<').replace('&gt;', '>')
    文本 = 文本.replace('&quot;', '"').replace('&#39;', "'")
    return 文本.strip()


def 提取摘要(文本, 最大长度=150):
    """从文本中提取摘要"""
    文本 = 清理文本(文本)
    if len(文本) <= 最大长度:
        return 文本
    # 在最大长度附近找最近的句号或空格
    截断位置 = 最大长度
    for 标点 in ['。', '！', '？', '\n', '，', ' ']:
        位置 = 文本.rfind(标点, 0, 最大长度 + 30)
        if 位置 > 最大长度 - 30:
            截断位置 = 位置 + 1
            break
    return 文本[:截断位置].strip()


def 生成原生资讯标题(标题, 来源):
    """为一手消息加中文重点标识，保留原始标题主体。"""
    原标题 = 清理文本(标题)
    if 原标题.startswith("【原生·"):
        return 原标题

    小写标题 = 原标题.lower()
    规则 = [
        ("发布", ["release", "launch", "introducing", "announce", "announcing", "released"]),
        ("模型", ["model", "gpt", "llm", "multimodal", "inference"]),
        ("研究", ["research", "paper", "benchmark", "dataset", "arxiv"]),
        ("开源", ["open source", "github", "weights", "library"]),
        ("安全", ["safety", "alignment", "policy", "preparedness"]),
        ("开发者", ["api", "developer", "sdk", "agents", "tool"]),
    ]
    重点 = "一手"
    for 标签, 关键词列表 in 规则:
        if any(关键词 in 小写标题 for 关键词 in 关键词列表):
            重点 = 标签
            break
    return f"【原生·{重点}】{原标题}"


# ============================================================
# DeepSeek AI 翻译 + 提炼（用于一手消息）
# ============================================================

DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
DEEPSEEK_MODEL = 'deepseek-chat'

def 翻译并提炼(原标题, 摘要):
    """调用 DeepSeek API 英译中+提炼要点。
    返回 (翻译后标题, 中文要点) 或 (原标题, '')。
    """
    if not DEEPSEEK_API_KEY:
        return 原标题, ''

    # 去掉 【原生·XXX】 前缀再翻译，翻译完再加回去
    前缀 = ''
    m = re.match(r'^(【原生·[^】]+】)', 原标题)
    if m:
        前缀 = m.group(1)
        原文标题 = 原标题[len(前缀):]
    else:
        原文标题 = 原标题

    try:
        import requests as req
        prompt = f'''你是一位AI新闻编辑。将以下英文AI资讯的标题翻译成中文，并提炼3-5个关键要点。

要求：
- 标题翻译准确，专业术语保持原样（如 GPT、LLM、RAG 等）
- 每行一条要点，用"• "开头，每条1-2句话
- 保留所有数字、日期、人名、模型名、组织名
- 如含技术性能数据必须在要点中保留
- 语气客观中立

输出格式（纯JSON，不要markdown标记）：
{{"title":"中文标题","points":"• 要点1\\n• 要点2\\n• 要点3"}}

标题：{原文标题}
内容：{摘要[:1000]}'''

        resp = req.post(
            'https://api.deepseek.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {DEEPSEEK_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': DEEPSEEK_MODEL, 'messages': [{'role': 'user', 'content': prompt}],
                  'max_tokens': 500, 'temperature': 0.3},
            timeout=30,
        )
        if not resp.ok:
            print(f'  [翻译] DeepSeek {resp.status_code}')
            return 原标题, ''

        content = resp.json()['choices'][0]['message']['content'].strip()
        # 清理可能的 markdown 代码块标记
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        结果 = json.loads(content)
        中文标题 = 结果.get('title', '').strip()
        要点 = 结果.get('points', '').strip()

        if 中文标题:
            return f'{前缀}{中文标题}', 要点
        return 原标题, ''

    except Exception as e:
        print(f'  [翻译] 异常: {type(e).__name__}')
        return 原标题, ''


def 提取标签(标题, 摘要):
    """从标题和摘要中提取关键词标签"""
    候选标签 = [
        "GPT-5", "GPT-4", "ChatGPT", "Claude", "Gemini", "DeepSeek",
        "Llama", "Qwen", "通义千问", "文心一言", "混元", "Mistral",
        "Sora", "Midjourney", "Stable Diffusion", "DALL-E",
        "OpenAI", "Anthropic", "Google", "Meta", "微软", "华为",
        "大模型", "开源", "多模态", "AI Agent", "具身智能",
        "人形机器人", "AI芯片", "视频生成", "AI绘画", "AI音乐",
        "AI医疗", "自动驾驶", "RAG", "向量数据库", "AI编程",
        "HuggingFace", "PyTorch", "NeurIPS", "ICML", "CVPR",
    ]
    文本 = f"{标题} {摘要}".lower()
    匹配标签 = []
    for 标签 in 候选标签:
        if 标签.lower() in 文本:
            匹配标签.append(标签)
    return 匹配标签[:6]  # 最多6个标签


# ============================================================
# 采集函数
# ============================================================

def 采集RSS来源(来源配置):
    """从RSS源采集文章"""
    文章列表 = []
    来源名称 = 来源配置["名称"]
    RSS地址 = 来源配置["RSS"]

    try:
        print(f"  [采集] 正在从 {来源名称} 获取 RSS：{RSS地址}")
        响应 = requests.get(RSS地址, headers=请求头, timeout=请求超时)
        响应.raise_for_status()

        源数据 = feedparser.parse(响应.content)

        if 源数据.bozo and not 源数据.entries:
            print(f"  [警告] {来源名称} RSS 解析异常：{源数据.bozo_exception}")
            return 文章列表

        条目数 = min(len(源数据.entries), 每源最大文章数)
        print(f"  [信息] {来源名称} 获取到 {len(源数据.entries)} 篇文章，处理前 {条目数} 篇")

        for 条目 in 源数据.entries[:条目数]:
            try:
                标题 = 清理文本(条目.get("title", ""))
                if not 标题 or len(标题) < 5:
                    continue

                摘要原文 = 条目.get("summary", "") or 条目.get("description", "")
                摘要 = 提取摘要(摘要原文)

                链接 = 条目.get("link", "")

                # 尝试获取发布日期
                日期 = ""
                if hasattr(条目, "published_parsed") and 条目.published_parsed:
                    try:
                        日期 = datetime(*条目.published_parsed[:6]).strftime("%Y-%m-%d")
                    except:
                        日期 = datetime.now().strftime("%Y-%m-%d")
                else:
                    日期 = datetime.now().strftime("%Y-%m-%d")

                分类 = 来源配置.get("固定分类") or 自动分类(标题, 摘要, 来源配置)
                if 来源配置.get("原生资讯"):
                    标题 = 生成原生资讯标题(标题, 来源名称)
                标签 = 提取标签(标题, 摘要)
                if 来源配置.get("原生资讯"):
                    标签 = list(dict.fromkeys(["原生资讯", 来源名称] + 标签))
                热度 = 计算热度(标题, 摘要)

                文章列表.append({
                    "id": 生成文章ID(标题, 来源名称),
                    "标题": 标题,
                    "摘要": 摘要,
                    "内容": 摘要,  # RSS通常只有摘要
                    "来源": 来源名称,
                    "分类": 分类,
                    "日期": 日期,
                    "热度": 热度,
                    "链接": 链接,
                    "标签": 标签,
                })
            except Exception as e:
                print(f"  [错误] 处理 {来源名称} 文章时出错：{e}")
                continue

    except requests.exceptions.Timeout:
        print(f"  [超时] {来源名称} 请求超时，跳过")
    except requests.exceptions.ConnectionError:
        print(f"  [连接失败] {来源名称} 无法连接，可能被屏蔽，跳过")
    except requests.exceptions.HTTPError as e:
        print(f"  [HTTP错误] {来源名称} 返回错误：{e}")
    except Exception as e:
        print(f"  [错误] 采集 {来源名称} 时发生异常：{e}")

    return 文章列表


def 采集API来源(来源配置):
    """从API接口采集文章"""
    文章列表 = []
    来源名称 = 来源配置["名称"]
    API地址 = 来源配置["RSS"]  # 配置中RSS字段复用为API地址

    try:
        print(f"  [采集] 正在从 {来源名称} 获取 API：{API地址}")
        响应 = requests.get(API地址, headers=请求头, timeout=请求超时)
        响应.raise_for_status()

        # 尝试解析JSON
        try:
            数据 = 响应.json()
        except:
            print(f"  [警告] {来源名称} API 返回的不是JSON格式")
            return 文章列表

        # 新浪科技API格式特殊处理
        条目列表 = 数据.get("result", {}).get("data", []) if isinstance(数据, dict) else []

        条目数 = min(len(条目列表), 每源最大文章数)
        print(f"  [信息] {来源名称} 获取到 {len(条目列表)} 篇文章，处理前 {条目数} 篇")

        for 条目 in 条目列表[:条目数]:
            try:
                标题 = 清理文本(条目.get("title", "") or 条目.get("intro", ""))
                if not 标题 or len(标题) < 5:
                    continue

                摘要 = 提取摘要(条目.get("intro", "") or 条目.get("summary", ""))
                链接 = 条目.get("url", "") or 条目.get("link", "")
                日期 = 条目.get("ctime", "") or 条目.get("pub_date", "")

                if 日期:
                    try:
                        日期 = datetime.fromtimestamp(int(日期)).strftime("%Y-%m-%d")
                    except:
                        日期 = datetime.now().strftime("%Y-%m-%d")
                else:
                    日期 = datetime.now().strftime("%Y-%m-%d")

                分类 = 来源配置.get("固定分类") or 自动分类(标题, 摘要, 来源配置)
                if 来源配置.get("原生资讯"):
                    标题 = 生成原生资讯标题(标题, 来源名称)
                标签 = 提取标签(标题, 摘要)
                if 来源配置.get("原生资讯"):
                    标签 = list(dict.fromkeys(["原生资讯", 来源名称] + 标签))
                热度 = 计算热度(标题, 摘要)

                文章列表.append({
                    "id": 生成文章ID(标题, 来源名称),
                    "标题": 标题,
                    "摘要": 摘要,
                    "内容": 摘要,
                    "来源": 来源名称,
                    "分类": 分类,
                    "日期": 日期,
                    "热度": 热度,
                    "链接": 链接,
                    "标签": 标签,
                })
            except Exception as e:
                print(f"  [错误] 处理 {来源名称} 文章时出错：{e}")
                continue

    except requests.exceptions.Timeout:
        print(f"  [超时] {来源名称} 请求超时，跳过")
    except requests.exceptions.ConnectionError:
        print(f"  [连接失败] {来源名称} 无法连接，跳过")
    except Exception as e:
        print(f"  [错误] 采集 {来源名称} 时发生异常：{e}")

    return 文章列表


def 采集单个来源(来源配置):
    """根据来源类型选择采集方式"""
    类型 = 来源配置.get("类型", "RSS")
    if 类型 == "RSS":
        return 采集RSS来源(来源配置)
    elif 类型 == "API":
        return 采集API来源(来源配置)
    else:
        print(f"  [警告] 未知来源类型：{类型}")
        return []


# ============================================================
# 去重与合并
# ============================================================

def 文章去重(新文章列表, 已有文章列表):
    """根据ID和标题相似度去重"""
    已有ID集合 = {a["id"] for a in 已有文章列表}
    已有标题集合 = {a["标题"].strip().lower() for a in 已有文章列表}

    去重后 = []
    重复数 = 0

    for 文章 in 新文章列表:
        # ID去重
        if 文章["id"] in 已有ID集合:
            重复数 += 1
            continue

        # 标题相似度去重（完全匹配）
        标题小写 = 文章["标题"].strip().lower()
        if 标题小写 in 已有标题集合:
            重复数 += 1
            continue

        # 模糊匹配：标题前30个字符相同视为重复
        标题前缀 = 标题小写[:30]
        if any(a["标题"].strip().lower()[:30] == 标题前缀 for a in 已有文章列表):
            重复数 += 1
            continue

        去重后.append(文章)

    if 重复数 > 0:
        print(f"  [去重] 去除了 {重复数} 篇重复文章")

    return 去重后


# ============================================================
# 主流程
# ============================================================

def 加载已有数据库():
    """加载现有的文章数据库"""
    if 数据库路径.exists():
        try:
            with open(数据库路径, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("[警告] 数据库文件损坏，将创建新数据库")
            return []
    return []


def 保存数据库(文章列表):
    """保存文章数据库"""
    # 确保目录存在
    数据库路径.parent.mkdir(parents=True, exist_ok=True)

    # 先写入临时文件，再替换（防止写入中断导致数据损坏）
    临时路径 = 数据库路径.with_suffix(".tmp")
    with open(临时路径, "w", encoding="utf-8") as f:
        json.dump(文章列表, f, ensure_ascii=False, indent=2)

    临时路径.replace(数据库路径)
    print(f"[保存] 数据库已更新，共 {len(文章列表)} 篇文章")


def 登记修改(新增数量):
    """铁律：任何智能体修改文件必须在修改登记中记录。
    本函数在自动采集脚本修改文章数据库后，将本次操作写入修改登记.json。"""
    try:
        登记数据 = {"修改历史": []}
        if 登记路径.exists():
            try:
                with open(登记路径, "r", encoding="utf-8") as f:
                    登记数据 = json.load(f)
            except (json.JSONDecodeError, IOError):
                登记数据 = {"修改历史": []}

        # 构建新记录
        新记录 = {
            "id": len(登记数据.get("修改历史", [])) + 1,
            "时间": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "智能体": 采集智能体名称,
            "操作人": 采集操作人,
            "修改文件": ["文章数据库.json"],
            "改动摘要": f"自动采集：新增 {新增数量} 篇文章",
            "改动原因": "GitHub Actions 定时自动采集最新AI资讯"
        }

        # 更新历史
        if "修改历史" not in 登记数据:
            登记数据["修改历史"] = []
        登记数据["修改历史"].insert(0, 新记录)

        # 更新文件最后修改记录
        if "files_last_modified" not in 登记数据:
            登记数据["files_last_modified"] = {}
        登记数据["files_last_modified"]["文章数据库.json"] = {
            "最后修改者": 采集智能体名称,
            "操作人": 采集操作人,
            "时间": 新记录["时间"]
        }

        登记数据["最后更新"] = 新记录["时间"]

        # 写入
        临时路径 = 登记路径.with_suffix(".tmp")
        with open(临时路径, "w", encoding="utf-8") as f:
            json.dump(登记数据, f, ensure_ascii=False, indent=2)
        临时路径.replace(登记路径)
        print(f"[登记] 已在修改登记中记录本次变更")

    except Exception as e:
        print(f"[登记] 警告：修改登记写入失败 - {e}")


def 生成内容摘要(文章列表):
    """为缺少内容的文章生成内容字段"""
    for 文章 in 文章列表:
        if not 文章.get("内容"):
            文章["内容"] = 文章.get("摘要", "")


def 采集金融资讯():
    """单独采集金融资讯，生成金融API"""
    print("\n" + "=" * 60)
    print("金融热点采集 · Financial Hot News API")
    print(f"运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    金融文章 = []
    for 来源 in 金融来源配置:
        来源名称 = 来源["名称"]
        print(f"\n--- {来源名称} ---")
        try:
            if 来源.get("类型") == "API":
                新文章 = 采集API来源(来源)
            else:
                新文章 = 采集RSS来源(来源)
            if 新文章:
                金融文章.extend(新文章)
                print(f"  [OK] {来源名称}：获取 {len(新文章)} 篇")
        except Exception as e:
            print(f"  [!!] {来源名称}：采集失败 - {e}")
        time.sleep(1)

    # 金融文章去重
    已有金融文章 = []
    if 金融API路径.exists():
        try:
            with open(金融API路径, "r", encoding="utf-8") as f:
                数据 = json.load(f)
                已有金融文章 = 数据.get("articles", [])
        except:
            pass

    # 去重
    去重后 = 文章去重(金融文章, 已有金融文章)

    # 合并：新文章在前
    全部金融文章 = 去重后 + 已有金融文章

    # 按热度排序
    全部金融文章.sort(key=lambda x: (x.get("热度", 50), x.get("日期", "")), reverse=True)

    # 限制最大条数
    if len(全部金融文章) > 金融API最大条数:
        全部金融文章 = 全部金融文章[:金融API最大条数]

    # 生成API格式
    api数据 = {
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "source": "极光引擎 · 金融热点API",
        "description": "实时金融热点资讯，按热度排序，每天自动更新。可直接 GET 请求获取 JSON。",
        "count": len(全部金融文章),
        "articles": 全部金融文章
    }

    # 写入API文件
    临时路径 = 金融API路径.with_suffix(".tmp")
    with open(临时路径, "w", encoding="utf-8") as f:
        json.dump(api数据, f, ensure_ascii=False, indent=2)
    临时路径.replace(金融API路径)
    print(f"\n[金融API] 已生成：{金融API路径}，共 {len(全部金融文章)} 条热点")
    return len(去重后)


def 主流程():
    """主执行流程"""
    print("=" * 60)
    print("极光引擎 · 每日AI资讯自动采集")
    print(f"运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 加载已有数据
    print(f"\n[步骤1] 加载已有数据库...")
    已有文章 = 加载已有数据库()
    print(f"  当前数据库共有 {len(已有文章)} 篇文章")

    # 2. 逐个来源采集
    print(f"\n[步骤2] 开始采集资讯（共 {len(资讯来源配置)} 个来源）...")
    所有新文章 = []
    成功数 = 0
    失败数 = 0

    for 来源 in 资讯来源配置:
        来源名称 = 来源["名称"]
        print(f"\n--- {来源名称} ---")
        try:
            新文章 = 采集单个来源(来源)
            if 新文章:
                去重后 = 文章去重(新文章, 已有文章 + 所有新文章)
                所有新文章.extend(去重后)
                print(f"  [OK] {来源名称}：获取 {len(新文章)} 篇，去重后 {len(去重后)} 篇")
                成功数 += 1
            else:
                print(f"  [--] {来源名称}：未获取到文章")
        except Exception as e:
            print(f"  [!!] {来源名称}：采集失败 - {e}")
            失败数 += 1

        # 请求间隔，避免被封
        time.sleep(1)

    print(f"\n[统计] 成功：{成功数}/{len(资讯来源配置)}，失败：{失败数}")
    print(f"[统计] 本轮共获取 {len(所有新文章)} 篇新文章")

    # 2.5 翻译原生资讯（一手消息）：英译中 + 提炼要点
    原生来源 = {'OpenAI 官方', 'Google DeepMind 官方', 'Hugging Face 官方', 'arXiv AI'}
    if DEEPSEEK_API_KEY and 所有新文章:
        print(f"\n[步骤2.5] 翻译原生资讯（一手消息）...")
        翻译数 = 0
        for 文章 in 所有新文章:
            if 文章.get('来源') in 原生来源 and not 文章.get('原标题'):
                原标题 = 文章['标题']
                中文标题, 要点 = 翻译并提炼(原标题, 文章.get('摘要', ''))
                if 中文标题 and 中文标题 != 原标题:
                    文章['原标题'] = 原标题
                    文章['标题'] = 中文标题
                    文章['中文提炼'] = 要点
                    翻译数 += 1
                    print(f'  ✓ [{文章["来源"]}] {原标题[:40]}... → {中文标题[:40]}')
                time.sleep(0.3)
        if 翻译数:
            print(f'  [翻译] 完成 {翻译数} 篇')
        else:
            print(f'  [翻译] 无新文章需要翻译')

    # 3. 合并数据库
    print(f"\n[步骤3] 合并数据库...")
    if 所有新文章:
        # 新文章插入到最前面
        合并后 = 所有新文章 + 已有文章

        # 补充内容字段
        生成内容摘要(合并后)

        # 限制数据库最大文章数（保留最新500篇）
        if len(合并后) > 500:
            print(f"  数据库超过500篇，截断保留最新500篇")
            合并后 = 合并后[:500]

        # 按日期排序（最新在前）
        合并后.sort(key=lambda x: x.get("日期", "2000-01-01"), reverse=True)

        保存数据库(合并后)
        print(f"  [OK] 数据库更新完成！新增 {len(所有新文章)} 篇，总计 {len(合并后)} 篇")

        # 铁律：任何智能体修改文件必须登记
        登记修改(len(所有新文章))
    else:
        print("  [--] 没有新文章，数据库保持不变")

    # 4. 输出新增文章标题
    if 所有新文章:
        print(f"\n[步骤4] 今日新增文章标题：")
        for i, 文章 in enumerate(所有新文章[:10], 1):
            print(f"  {i}. [{文章['来源']}] {文章['标题'][:60]}")

    print(f"\n{'=' * 60}")
    print("采集任务完成。")
    print(f"{'=' * 60}")

    # 6. 采集金融资讯 + 生成金融API
    print(f"\n[步骤6] 采集金融热点资讯...")
    try:
        金融新增 = 采集金融资讯()
        print(f"[金融API] 新增 {金融新增} 条金融热点")
    except Exception as e:
        print(f"[金融API] 采集失败：{e}")

    return len(所有新文章)


# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    try:
        新增数量 = 主流程()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n[中断] 用户取消了采集任务")
        sys.exit(1)
    except Exception as e:
        print(f"\n[致命错误] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
