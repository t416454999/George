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
# 资讯来源配置（全部可在中国内地直连）
# ============================================================

资讯来源配置 = [
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

                分类 = 自动分类(标题, 摘要, 来源配置)
                标签 = 提取标签(标题, 摘要)
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

                分类 = 自动分类(标题, 摘要, 来源配置)
                标签 = 提取标签(标题, 摘要)
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
        print(f"  [去重] 从 {来源名称} 去除了 {重复数} 篇重复文章")

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


def 生成内容摘要(文章列表):
    """为缺少内容的文章生成内容字段"""
    for 文章 in 文章列表:
        if not 文章.get("内容"):
            文章["内容"] = 文章.get("摘要", "")


def 主流程():
    """主执行流程"""
    print("=" * 60)
    print("🌌 极光引擎 - 每日AI资讯自动采集")
    print(f"📅 运行时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 加载已有数据
    print("\n[步骤1] 加载已有数据库...")
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
                print(f"  ✅ {来源名称}：获取 {len(新文章)} 篇，去重后 {len(去重后)} 篇")
                成功数 += 1
            else:
                print(f"  ⚠️ {来源名称}：未获取到文章")
        except Exception as e:
            print(f"  ❌ {来源名称}：采集失败 - {e}")
            失败数 += 1

        # 请求间隔，避免被封
        time.sleep(1)

    print(f"\n[统计] 成功：{成功数}/{len(资讯来源配置)}，失败：{失败数}")
    print(f"[统计] 本轮共获取 {len(所有新文章)} 篇新文章")

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
        print(f"  ✅ 数据库更新完成！新增 {len(所有新文章)} 篇，总计 {len(合并后)} 篇")
    else:
        print("  ℹ️ 没有新文章，数据库保持不变")

    # 4. 输出新增文章标题
    if 所有新文章:
        print(f"\n[步骤4] 今日新增文章标题：")
        for i, 文章 in enumerate(所有新文章[:10], 1):
            print(f"  {i}. [{文章['来源']}] {文章['标题'][:60]}")

    print(f"\n{'=' * 60}")
    print(f"🌌 采集任务完成！")
    print(f"{'=' * 60}")

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
