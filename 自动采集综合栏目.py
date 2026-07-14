#!/usr/bin/env python3
"""极光引擎：国际形势、世界杯、人文艺术、情感四个独立栏目采集器。"""

from __future__ import annotations

import html
import json
import os
import random
import re
import time
import zlib
from io import BytesIO
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import feedparser
import requests
from PIL import Image, UnidentifiedImageError


根目录 = Path(__file__).resolve().parent
请求头 = {
    "User-Agent": "AuroraEngine/1.0 (+https://boke.jgyq.me)",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
}
超时 = 30
云端运行 = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("AURORA_CLOUD_RUNTIME") == "github-actions"
图片缓存目录 = 根目录 / "assets" / "art"
新闻图片缓存目录 = 根目录 / "assets" / "media"
栏目封面 = {
    "国际形势": "assets/covers/international.svg",
    "世界杯": "assets/covers/world-cup.svg",
    "人文艺术": "assets/covers/humanities.svg",
    "情感": "assets/covers/emotion.svg",
}
深度求索分类调用 = {"国际形势": 0, "人文艺术": 0, "情感": 0, "世界杯": 0, "Rijksmuseum": 0, "Art Institute of Chicago": 0}
深度求索默认配额 = {"国际形势": 4, "人文艺术": 4, "情感": 4, "世界杯": 0, "Rijksmuseum": 4, "Art Institute of Chicago": 4}
深度求索标题分类调用 = {"国际形势": 0, "人文艺术": 0, "情感": 0, "世界杯": 0, "Rijksmuseum": 0, "Art Institute of Chicago": 0}
深度求索标题默认配额 = {"国际形势": 8, "人文艺术": 14, "情感": 24, "世界杯": 0, "Rijksmuseum": 14, "Art Institute of Chicago": 14}
深度求索已翻译标题 = set()


def 现在字符串():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def 稳定ID(*内容):
    return zlib.crc32("|".join(str(x) for x in 内容).encode("utf-8")) & 0xFFFFFFFF


def 清理文本(文本, 最大长度=240):
    if not 文本:
        return ""
    文本 = re.sub(r"<[^>]+>", " ", str(文本))
    文本 = html.unescape(文本)
    文本 = re.sub(r"\s+", " ", 文本).strip()
    return 文本[:最大长度].rstrip("，。；;,. ")


def 规范日期(值):
    if not 值:
        return datetime.now().strftime("%Y-%m-%d")
    文本 = str(值).strip()
    try:
        return parsedate_to_datetime(文本).astimezone().strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        匹配 = re.search(r"(20\d{2})[-/]?(\d{2})[-/]?(\d{2})", 文本)
        return "-".join(匹配.groups()) if 匹配 else datetime.now().strftime("%Y-%m-%d")


def 翻译成中文(文本):
    """只翻译短文本；失败时保留原文，避免单个翻译服务拖垮采集。"""
    文本 = 清理文本(文本, 420)
    if not 文本 or re.search(r"[\u4e00-\u9fff]", 文本):
        return 文本
    if not 云端运行:
        return 文本
    try:
        响应 = requests.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "auto", "tl": "zh-CN", "dt": "t", "q": 文本},
            headers=请求头,
            timeout=12,
        )
        响应.raise_for_status()
        return "".join(x[0] for x in 响应.json()[0] if x and x[0]).strip() or 文本
    except Exception:
        return 文本


def _合格中文标题(标题):
    标题 = 清理文本(标题, 80).strip("《》‘’“”\"'")
    if not 标题 or "�" in 标题 or not re.search(r"[\u4e00-\u9fff]", 标题):
        return ""
    # 防止模型把解释、原文或多个备选标题一起塞进标题栏。
    if len(标题) > 48 or "\n" in 标题 or any(x in 标题 for x in ("翻译如下", "中文标题：", "原标题：")):
        return ""
    return 标题


def _保守艺术标题(原标题, 回退提示=""):
    """无模型时不猜作品含义；只翻译明确的常见馆藏题名。"""
    原标题 = 清理文本(原标题, 150)
    小写 = 原标题.casefold().strip()
    完整词典 = {
        "untitled": "无题", "self-portrait": "自画像", "self portrait": "自画像",
        "portrait of a woman": "女子肖像", "portrait of a man": "男子肖像",
        "landscape": "风景", "still life": "静物", "the family": "家庭",
        "mother and child": "母与子", "the lovers": "恋人", "love": "爱",
        "solitude": "独处", "music": "音乐", "poetry": "诗歌",
    }
    if 小写 in 完整词典:
        return 完整词典[小写]
    # 仅在题名结构非常明确时做有限替换，避免机械翻译制造荒谬标题。
    匹配 = re.fullmatch(r"portrait of (?:a |an |the )?([\w .'-]{1,36})", 小写)
    if 匹配:
        return "人物肖像"
    return "馆藏作品"


def 生成中文标题(原标题, 分类, 旧文章=None, 回退提示=""):
    """标题翻译使用独立配额，永远保留原标题供页面以小字展示。"""
    原标题 = 清理文本(原标题, 180)
    if not 原标题 or re.search(r"[\u4e00-\u9fff]", 原标题):
        return 原标题
    密钥 = os.environ.get("DEEPSEEK_API_KEY", "").strip() if 云端运行 else ""
    旧标题 = _合格中文标题((旧文章 or {}).get("标题", ""))
    if 旧标题 and (旧文章 or {}).get("标题翻译方式") in {"DeepSeek", "人工校订"}:
        return 旧标题
    try:
        配额 = json.loads(os.environ.get("DEEPSEEK_TITLE_QUOTAS", "{}"))
    except json.JSONDecodeError:
        配额 = {}
    最大调用 = max(0, int(配额.get(分类, 深度求索标题默认配额.get(分类, 0))))
    if 密钥 and 深度求索标题分类调用.get(分类, 0) < 最大调用:
        提示 = (
            "把下面的英文标题准确、简洁地译成自然中文。它是页面正标题；不要解释，不要补充原文没有的信息。"
            "艺术品题名应像博物馆图录；论文题名应保持研究限定词。"
            "只输出 JSON：{\"中文标题\":\"...\"}。\n"
            f"分类：{分类}\n原标题：{原标题}"
        )
        try:
            深度求索标题分类调用[分类] = 深度求索标题分类调用.get(分类, 0) + 1
            响应 = requests.post(
                os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"),
                headers={"Authorization": f"Bearer {密钥}", "Content-Type": "application/json"},
                json={
                    "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                    "messages": [{"role": "user", "content": 提示}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
                timeout=35,
            )
            响应.raise_for_status()
            内容 = _提取JSON对象(响应.json()["choices"][0]["message"]["content"])
            标题 = _合格中文标题(内容.get("中文标题", ""))
            if 标题:
                深度求索已翻译标题.add((分类, 原标题))
                return 标题
        except Exception as e:
            print(f"[提示] DeepSeek 标题翻译失败，使用保守标题：{e}")

    if 旧标题:
        return 旧标题

    if 分类 == "人文艺术":
        return _保守艺术标题(原标题, 回退提示)
    # 非艺术题名仍可使用短文本翻译服务；返回结果须通过中文与乱码校验。
    return _合格中文标题(翻译成中文(原标题)) or _合格中文标题(回退提示) or "外文资讯"


def 旧文章索引(文件名):
    索引 = {}
    for 项 in 读取旧数据(文件名).get("articles", []):
        if 项.get("id") is not None:
            索引[("id", str(项["id"]))] = 项
        if 项.get("链接"):
            索引.setdefault(("链接", 项["链接"]), 项)
    return 索引


def 匹配旧文章(索引, 文章):
    return (
        索引.get(("id", str(文章.get("id"))))
        or 索引.get(("链接", 文章.get("链接")))
    )


def _提取JSON对象(文本):
    匹配 = re.search(r"\{.*\}", 文本 or "", re.S)
    if not 匹配:
        return {}
    try:
        return json.loads(匹配.group(0))
    except json.JSONDecodeError:
        return {}


def _回退杂志内容(文章, 素材=""):
    """只依据已有元数据编写，不补造事实，也不复制来源全文。"""
    分类 = 文章.get("分类", "专题")
    标题 = 清理文本(文章.get("标题"), 120)
    来源 = 清理文本(文章.get("来源"), 80) or "原始来源"
    素材 = 清理文本(素材 or 文章.get("摘要"), 460)
    if 分类 == "世界杯":
        if 文章.get("来源") in ("openfootball/worldcup.json", "football-data.org"):
            导语 = 清理文本(文章.get("摘要"), 110) or "赛程信息以数据源最新更新为准。"
            要点 = [x.strip() for x in re.split(r"[·|]", 文章.get("摘要", "")) if x.strip()][:3]
            正文 = f"{标题}。{导语} 本页提供便于国内访问的赛程速览；临场调整、最终比分与判罚请以赛事官方信息为准。"
        else:
            导语 = 素材[:110] or "关于2026世界杯的最新动态。"
            要点 = ["发生了什么", "涉及哪些球队或人物", "后续值得关注什么"]
            正文 = f"{素材 or 标题}。本短稿依据公开新闻标题与摘要整理，帮助了解2026世界杯动态；完整报道请查阅原文。"
    elif 分类 == "人文艺术":
        导语 = f"从馆藏资料出发，认识《{标题}》及其创作背景。"
        要点 = [x.strip() for x in re.split(r"[·|]", 文章.get("摘要", "")) if x.strip()][:3]
        正文 = f"《{标题}》现由{来源}收录。{素材}。这里呈现的是基于开放馆藏元数据整理的中文导览，适合先看作品、再沿原出处继续探索。"
    elif 分类 == "情感":
        导语 = f"这项研究为理解“{标题}”提供了一个观察角度。"
        要点 = ["关注研究讨论的问题", "区分研究关联与因果结论", "结合原论文理解适用范围"]
        正文 = f"{素材 or 标题}。这是基于论文题目与摘要整理的知识导读，只帮助理解研究线索，不替代原论文，也不构成诊断、治疗或个体化医疗建议。"
    else:
        导语 = 素材[:110] or f"从{来源}的最新信息观察“{标题}”。"
        要点 = ["发生了什么", "涉及哪些主体", "后续值得关注什么"]
        正文 = f"{素材 or 标题}。本短稿依据公开标题与摘要整理，用于帮助读者快速了解事件脉络；信息仍可能更新，请结合原出处核对。"
    return {
        "导语": 清理文本(导语, 140),
        "要点": [清理文本(x, 80) for x in 要点 if 清理文本(x, 80)][:3],
        "正文": 清理文本(正文, 760),
        "编辑方式": "规则整理",
    }


def 生成杂志内容(文章, 素材="", 旧文章=None):
    """优先复用已生成短稿；可选 DeepSeek 只编辑给定素材，不抓取或复刻全文。"""
    if (
        旧文章 and 旧文章.get("编辑方式") == "DeepSeek"
        and all(旧文章.get(k) for k in ("导语", "要点", "正文"))
    ):
        return {k: 旧文章[k] for k in ("导语", "要点", "正文", "编辑方式")}
    回退 = _回退杂志内容(文章, 素材)
    密钥 = os.environ.get("DEEPSEEK_API_KEY", "").strip() if 云端运行 else ""
    分类 = 文章.get("分类", "")
    try:
        配额 = json.loads(os.environ.get("DEEPSEEK_CATEGORY_QUOTAS", "{}"))
    except json.JSONDecodeError:
        配额 = {}
    最大调用 = max(0, int(配额.get(分类, 深度求索默认配额.get(分类, 0))))
    if not 密钥 or 深度求索分类调用.get(分类, 0) >= 最大调用:
        return 回退
    输入素材 = 清理文本(素材 or 文章.get("摘要"), 1600)
    if not 输入素材:
        return 回退
    提示 = (
        "你是中文杂志编辑。只能依据下方元数据和摘要改写，不得补造事实，不得大段翻译或复刻原文。"
        "输出严格 JSON：导语(不超过80字)、要点(3条，每条不超过45字)、正文(250至450字)。"
        "国际内容保持中性；艺术内容说明馆藏语境；情感研究必须写明不构成医疗建议，避免诊断和治疗建议。\n"
        f"分类：{文章.get('分类')}\n标题：{文章.get('标题')}\n来源：{文章.get('来源')}\n素材：{输入素材}"
    )
    try:
        深度求索分类调用[分类] = 深度求索分类调用.get(分类, 0) + 1
        响应 = requests.post(
            os.environ.get("DEEPSEEK_API_URL", "https://api.deepseek.com/chat/completions"),
            headers={"Authorization": f"Bearer {密钥}", "Content-Type": "application/json"},
            json={
                "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
                "messages": [{"role": "user", "content": 提示}],
                "temperature": 0.3,
                "response_format": {"type": "json_object"},
            },
            timeout=45,
        )
        响应.raise_for_status()
        内容 = _提取JSON对象(响应.json()["choices"][0]["message"]["content"])
        导语 = 清理文本(内容.get("导语"), 140)
        要点 = [清理文本(x, 80) for x in 内容.get("要点", []) if 清理文本(x, 80)][:3]
        正文 = 清理文本(内容.get("正文"), 760)
        return {"导语": 导语, "要点": 要点, "正文": 正文, "编辑方式": "DeepSeek"} if 导语 and 要点 and 正文 else 回退
    except Exception as e:
        print(f"[提示] DeepSeek 编辑失败，使用安全短稿：{e}")
        return 回退


def 补充杂志字段(文章, 素材="", 旧文章=None):
    文章.update(生成杂志内容(文章, 素材, 旧文章))
    文章["原文链接"] = 文章.get("链接", "")
    文章["出处说明"] = f"根据{文章.get('来源', '原始来源')}公开元数据/摘要整理，非原文转载。"
    文章.setdefault("版权", "标题与摘要版权归原发布者；本站短稿为资料性改写")
    文章.setdefault("封面", 栏目封面.get(文章.get("分类"), ""))
    return 文章


def 下载并压缩图片(图片链接, 缓存目录, 文件前缀, 来源ID, 允许域名后缀):
    """由云端任务缓存明确允许再发布的真实来源图，并限制格式、体积与域名。"""
    图片链接 = 安全链接(图片链接)
    主机 = (urlparse(图片链接).hostname or "").lower()
    if not 图片链接 or not any(主机 == x or 主机.endswith("." + x) for x in 允许域名后缀):
        return ""
    缓存目录.mkdir(parents=True, exist_ok=True)
    已有 = 缓存目录 / f"{文件前缀}-{来源ID}.webp"
    if 已有.is_file() and 1024 < 已有.stat().st_size <= 300 * 1024:
        return 已有.relative_to(根目录).as_posix()
    if not 云端运行:
        # 本机只读取已存在的站点缓存；持续下载、校验和压缩只交给 GitHub Actions。
        return ""
    临时 = 缓存目录 / f".{文件前缀}-{来源ID}.webp.tmp"
    try:
        with requests.get(图片链接, headers=请求头, timeout=超时, stream=True) as 响应:
            响应.raise_for_status()
            最终主机 = (urlparse(响应.url).hostname or "").lower()
            if not any(最终主机 == x or 最终主机.endswith("." + x) for x in 允许域名后缀):
                raise ValueError("图片重定向到了未授权域名")
            类型 = 响应.headers.get("Content-Type", "").split(";")[0].lower()
            if 类型 not in {"image/jpeg", "image/png", "image/webp"}:
                raise ValueError(f"不支持的图片类型：{类型}")
            总量 = 0
            原图 = BytesIO()
            for 块 in 响应.iter_content(64 * 1024):
                if not 块:
                    continue
                总量 += len(块)
                if 总量 > 4 * 1024 * 1024:
                    raise ValueError("原图超过 4 MiB 下载限制")
                原图.write(块)
        if 总量 < 1024:
            raise ValueError("图片内容过小")
        原图.seek(0)
        with Image.open(原图) as 图像:
            图像.load()
            if 图像.width * 图像.height > 40_000_000:
                raise ValueError("图片像素尺寸异常")
            图像.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            if 图像.mode not in ("RGB", "RGBA"):
                图像 = 图像.convert("RGB")
            # 逐级压缩，通常在 60–180KB；极复杂图仍不得超过 300KB。
            for 质量 in (80, 72, 64, 56):
                图像.save(临时, "WEBP", quality=质量, method=6)
                if 临时.stat().st_size <= 250 * 1024:
                    break
            if 临时.stat().st_size > 300 * 1024:
                raise ValueError("压缩后图片仍超过 300 KiB")
        临时.replace(已有)
        return 已有.relative_to(根目录).as_posix()
    except (OSError, ValueError, requests.RequestException, UnidentifiedImageError) as e:
        临时.unlink(missing_ok=True)
        print(f"[提示] 真实图片缓存失败 {文件前缀}-{来源ID}：{e}")
        return ""


def 下载馆藏图片(图片链接, 作品ID):
    """The Met Open Access 公共领域作品图；仅在 GitHub Actions 中持续更新。"""
    return 下载并压缩图片(
        图片链接, 图片缓存目录, "met", 作品ID,
        {"metmuseum.org", "images.metmuseum.org"},
    )


def 下载Rijksmuseum图片(图片链接, 作品ID):
    """Rijksmuseum 公共领域作品图。"""
    return 下载并压缩图片(
        图片链接, 图片缓存目录, "rijks", 作品ID,
        {"rijksmuseum.org"},
    )


def 下载芝加哥图片(图片链接, 作品ID):
    """Art Institute of Chicago CC0 作品图。"""
    return 下载并压缩图片(
        图片链接, 图片缓存目录, "aic", 作品ID,
        {"artic.edu"},
    )


def 下载联合国RSS图片(图片链接, 文章ID):
    """RSS enclosure 是联合国主动提供的配图；其他新闻图片不复制到本站。"""
    return 下载并压缩图片(
        图片链接, 新闻图片缓存目录, "un", 文章ID,
        {"unitednations.entermediadb.net", "news.un.org"},
    )


def 清理馆藏缓存(保留路径):
    """仅清理本站专用缓存；保留本周与上周最多 28 张，防止仓库无限增长。"""
    保留名称 = {Path(x).name for x in 保留路径 if x}
    文件 = sorted(
        list(图片缓存目录.glob("met-*.webp"))
        + list(图片缓存目录.glob("rijks-*.webp"))
        + list(图片缓存目录.glob("aic-*.webp")),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    for 路径 in 文件:
        if 路径.name not in 保留名称 and 文件.index(路径) >= 28:
            路径.unlink(missing_ok=True)


def 清理新闻图片缓存(保留路径):
    保留名称 = {Path(x).name for x in 保留路径 if x}
    文件 = sorted(新闻图片缓存目录.glob("un-*.webp"), key=lambda p: p.stat().st_mtime, reverse=True)
    for 序号, 路径 in enumerate(文件):
        if 路径.name not in 保留名称 and 序号 >= 56:
            路径.unlink(missing_ok=True)


def 安全链接(链接):
    try:
        解析 = urlparse(str(链接))
        return str(链接) if 解析.scheme in {"http", "https"} else ""
    except Exception:
        return ""


def 读取旧数据(文件名):
    路径 = 根目录 / 文件名
    try:
        return json.loads(路径.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def 原子保存(文件名, 数据):
    路径 = 根目录 / 文件名
    临时路径 = 路径.with_suffix(路径.suffix + ".tmp")
    临时路径.write_text(json.dumps(数据, ensure_ascii=False, indent=2), encoding="utf-8")
    临时路径.replace(路径)
    print(f"[保存] {文件名}：{len(数据.get('articles', []))} 条")


def 栏目数据(分类, 来源, 说明, 文章, 状态="ok", 提示=""):
    return {
        "updated": 现在字符串(),
        "category": 分类,
        "source": 来源,
        "description": 说明,
        "status": 状态,
        "message": 提示,
        "count": len(文章),
        "articles": 文章,
    }


def 合并去重(*文章组, 最大条数=30):
    结果, 已有 = [], set()
    for 文章 in (项 for 组 in 文章组 for 项 in 组):
        键 = (文章.get("链接") or 文章.get("标题", "")).strip().lower()
        if not 键 or 键 in 已有:
            continue
        已有.add(键)
        结果.append(文章)
    # 保留来源优先级：调用方把可信度更高的来源放在前面。
    return 结果[:最大条数]


def 提取RSS配图(条目):
    """只读取 RSS 明示的图片字段，不访问文章全文页面。"""
    候选 = []
    for 字段 in ("media_content", "media_thumbnail"):
        for 项 in 条目.get(字段, []) or []:
            if isinstance(项, dict):
                候选.append(项.get("url") or 项.get("href"))
    for 项 in 条目.get("enclosures", []) or []:
        if isinstance(项, dict) and str(项.get("type", "")).startswith("image/"):
            候选.append(项.get("href") or 项.get("url"))
    for 候选链接 in 候选:
        链接 = 安全链接(候选链接)
        if 链接:
            return 链接
    return ""


def 采集联合国中文新闻():
    地址 = "https://news.un.org/feed/subscribe/zh/news/all/rss.xml"
    响应 = requests.get(地址, headers=请求头, timeout=超时)
    响应.raise_for_status()
    feed = feedparser.parse(响应.content)
    文章, 本轮图片 = [], []
    for 条目 in feed.entries[:24]:
        标题 = 清理文本(条目.get("title"), 150)
        链接 = 安全链接(条目.get("link"))
        if not 标题 or not 链接:
            continue
        摘要 = 清理文本(条目.get("summary") or 条目.get("description"), 220)
        日期 = 规范日期(条目.get("published") or 条目.get("updated"))
        文章ID = 稳定ID(标题, 链接)
        原始图片 = 提取RSS配图(条目)
        本地图 = 下载联合国RSS图片(原始图片, 文章ID) if 原始图片 else ""
        文章.append({
            "id": 文章ID, "标题": 标题, "摘要": 摘要,
            "来源": "联合国新闻", "分类": "国际形势", "日期": 日期,
            "链接": 链接, "标签": ["国际", "联合国"],
            "图片": 本地图 or 栏目封面["国际形势"],
            "封面": 本地图 or 栏目封面["国际形势"],
            "原始图片": 原始图片,
        })
        if 本地图:
            本轮图片.append(本地图)
    清理新闻图片缓存(本轮图片)
    return 文章


def 采集GDELT():
    参数 = {
        "query": '(diplomacy OR ceasefire OR summit OR sanctions OR "peace talks")',
        "mode": "artlist", "format": "json", "maxrecords": 20,
        "sort": "datedesc", "timespan": "2d",
    }
    响应 = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params=参数, headers=请求头, timeout=超时)
    响应.raise_for_status()
    文章 = []
    旧索引 = 旧文章索引("国际形势.json")
    for 条目 in 响应.json().get("articles", []):
        原标题 = 清理文本(条目.get("title"), 160)
        链接 = 安全链接(条目.get("url"))
        if not 原标题 or not 链接:
            continue
        临时项 = {"id": 稳定ID(原标题, 链接), "链接": 链接}
        旧项 = 匹配旧文章(旧索引, 临时项)
        标题 = 生成中文标题(原标题, "国际形势", 旧项)
        域名 = 清理文本(条目.get("domain"), 80) or urlparse(链接).netloc
        原始图片 = 安全链接(条目.get("socialimage"))
        文章.append({
            "id": 临时项["id"], "标题": 标题,
            "原标题": 原标题,
            "标题翻译方式": "DeepSeek" if ("国际形势", 原标题) in 深度求索已翻译标题 else ((旧项 or {}).get("标题翻译方式") or "短译/历史复用"),
            "摘要": f"全球新闻索引收录的 {域名} 最新报道，点击阅读原文。",
            "来源": 域名 or "GDELT", "分类": "国际形势",
            "日期": 规范日期(条目.get("seendate")), "链接": 链接,
            "标签": ["国际", "全球媒体"], "原始图片": 原始图片,
            # GDELT 只索引第三方图片，版权不明，不复制；由栏目封面安全回退。
            "图片": 栏目封面["国际形势"], "封面": 栏目封面["国际形势"],
        })
    return 文章


def 采集国际形势():
    旧文章 = 读取旧数据("国际形势.json").get("articles", [])
    旧索引 = 旧文章索引("国际形势.json")
    联合国文章, gdelt文章, 错误 = [], [], []
    try:
        联合国文章 = 采集联合国中文新闻()
    except Exception as e:
        错误.append(f"联合国新闻：{e}")
    try:
        gdelt文章 = 采集GDELT()
    except Exception as e:
        错误.append(f"GDELT：{e}")
    文章 = 合并去重(联合国文章, gdelt文章, 旧文章, 最大条数=40)
    if not 文章:
        raise RuntimeError("；".join(错误) or "没有获取到国际形势数据")
    for 项 in 文章:
        补充杂志字段(项, 项.get("摘要", ""), 匹配旧文章(旧索引, 项))
    return 栏目数据(
        "国际形势", "联合国新闻 / GDELT",
        "全球局势与外交动态；仅展示摘要并链接至原始来源。", 文章,
        "partial" if 错误 else "ok", "；".join(错误),
    )


def 比赛阶段中文(阶段):
    return {
        "GROUP_STAGE": "小组赛", "LAST_32": "32强", "LAST_16": "16强",
        "QUARTER_FINALS": "四分之一决赛", "SEMI_FINALS": "半决赛",
        "THIRD_PLACE": "三四名决赛", "FINAL": "决赛",
    }.get(阶段 or "", 阶段 or "世界杯")


世界杯队名中文 = {
    "Algeria": "阿尔及利亚", "Argentina": "阿根廷", "Australia": "澳大利亚",
    "Austria": "奥地利", "Belgium": "比利时", "Bosnia & Herzegovina": "波黑",
    "Brazil": "巴西", "Canada": "加拿大", "Cape Verde": "佛得角",
    "Colombia": "哥伦比亚", "Croatia": "克罗地亚", "Curaçao": "库拉索",
    "Czech Republic": "捷克", "DR Congo": "刚果（金）", "Ecuador": "厄瓜多尔",
    "Egypt": "埃及", "England": "英格兰", "France": "法国", "Germany": "德国",
    "Ghana": "加纳", "Haiti": "海地", "Iran": "伊朗", "Iraq": "伊拉克",
    "Ivory Coast": "科特迪瓦", "Japan": "日本", "Jordan": "约旦",
    "Mexico": "墨西哥", "Morocco": "摩洛哥", "Netherlands": "荷兰",
    "New Zealand": "新西兰", "Norway": "挪威", "Panama": "巴拿马",
    "Paraguay": "巴拉圭", "Portugal": "葡萄牙", "Qatar": "卡塔尔",
    "Saudi Arabia": "沙特阿拉伯", "Scotland": "苏格兰", "Senegal": "塞内加尔",
    "South Africa": "南非", "South Korea": "韩国", "Spain": "西班牙",
    "Sweden": "瑞典", "Switzerland": "瑞士", "Tunisia": "突尼斯",
    "Turkey": "土耳其", "Uruguay": "乌拉圭", "USA": "美国",
    "Uzbekistan": "乌兹别克斯坦",
}


def _世界杯比赛胜负(比赛):
    """比分已确定时返回胜方/负方的原始队名；未赛或平局则返回空值。"""
    得分 = 比赛.get("score") or {}
    最终比分 = 得分.get("p") or 得分.get("et") or 得分.get("ft") or []
    if len(最终比分) != 2 or any(x is None for x in 最终比分) or 最终比分[0] == 最终比分[1]:
        return None, None
    主队, 客队 = 比赛.get("team1"), 比赛.get("team2")
    return (主队, 客队) if 最终比分[0] > 最终比分[1] else (客队, 主队)


def 世界杯席位中文(席位, 比赛索引, 已访问=None):
    """把 W101/L101 等晋级路径解析为真实球队或可读席位，绝不把内部代码交给读者。"""
    席位 = 清理文本(席位, 100)
    if not 席位 or 席位.upper() in {"TBD", "TBA", "TO BE DETERMINED"}:
        return "待定席位"
    if 席位 in 世界杯队名中文:
        return 世界杯队名中文[席位]

    路径 = re.fullmatch(r"([WL])(\d+)", 席位, re.IGNORECASE)
    if 路径:
        胜负, 场次文本 = 路径.groups()
        场次 = int(场次文本)
        已访问 = set(已访问 or ())
        if 场次 in 已访问:
            return f"第{场次}场{'胜者' if 胜负.upper() == 'W' else '负者'}"
        上一场 = 比赛索引.get(场次)
        if not 上一场:
            return f"第{场次}场{'胜者' if 胜负.upper() == 'W' else '负者'}"
        已访问.add(场次)
        胜方, 负方 = _世界杯比赛胜负(上一场)
        已确定 = 胜方 if 胜负.upper() == "W" else 负方
        if 已确定:
            return 世界杯席位中文(已确定, 比赛索引, 已访问)
        主队 = 世界杯席位中文(上一场.get("team1"), 比赛索引, 已访问)
        客队 = 世界杯席位中文(上一场.get("team2"), 比赛索引, 已访问)
        结果 = "胜者" if 胜负.upper() == "W" else "负者"
        return f"{主队}/{客队}{结果}"

    小组席位 = re.fullmatch(r"([123])([A-L])", 席位, re.IGNORECASE)
    if 小组席位:
        名次, 小组 = 小组席位.groups()
        return f"{小组.upper()}组第{名次}"
    if "play-off" in 席位.lower() or "playoff" in 席位.lower():
        return "附加赛胜者"
    return 席位


def 采集OpenFootball世界杯():
    地址 = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
    响应 = requests.get(地址, headers=请求头, timeout=超时)
    响应.raise_for_status()
    比赛列表 = 响应.json().get("matches", [])
    比赛索引 = {比赛.get("num"): 比赛 for 比赛 in 比赛列表 if 比赛.get("num") is not None}
    今天 = datetime.now().date()
    文章 = []
    for 序号, 比赛 in enumerate(比赛列表, 1):
        日期文本 = 比赛.get("date", "")
        时间 = 比赛.get("time") or "时间待定"
        try:
            时区匹配 = re.fullmatch(r"(\d{1,2}):(\d{2}) UTC([+-]\d+)", 时间)
            if 时区匹配:
                时, 分, 偏移 = map(int, 时区匹配.groups())
                场地时间 = datetime.strptime(日期文本, "%Y-%m-%d").replace(
                    hour=时, minute=分, tzinfo=timezone(timedelta(hours=偏移))
                )
                本地时间 = 场地时间.astimezone()
                比赛日期 = 本地时间.date()
                时间说明 = "北京时间 " + 本地时间.strftime("%m月%d日 %H:%M")
            else:
                比赛日期 = datetime.strptime(日期文本, "%Y-%m-%d").date()
                时间说明 = f"{日期文本} {时间}"
        except ValueError:
            比赛日期 = 今天
            时间说明 = f"{日期文本} {时间}"
        原主队, 原客队 = 比赛.get("team1"), 比赛.get("team2")
        主队 = 世界杯席位中文(原主队, 比赛索引)
        客队 = 世界杯席位中文(原客队, 比赛索引)
        得分 = 比赛.get("score") or {}
        最终比分 = 得分.get("p") or 得分.get("et") or 得分.get("ft") or []
        有比分 = len(最终比分) == 2 and all(x is not None for x in 最终比分)
        比分 = f"{最终比分[0]} : {最终比分[1]}" if 有比分 else "vs"
        阶段英文 = 比赛.get("round") or 比赛.get("group") or "World Cup"
        阶段映射 = {
            "Round of 32": "32强", "Round of 16": "16强", "Quarter-final": "四分之一决赛",
            "Semi-final": "半决赛", "Match for third place": "三四名决赛", "Final": "决赛",
        }
        比赛日 = re.fullmatch(r"Matchday (\d+)", 阶段英文)
        阶段 = f"第{比赛日.group(1)}比赛日" if 比赛日 else 阶段映射.get(阶段英文, 阶段英文)
        场地 = 比赛.get("ground") or "场地待定"
        状态 = "已结束" if 有比分 else ("今日比赛" if 比赛日期 == 今天 else "未开赛")
        赛制说明 = " · 点球大战" if 得分.get("p") else (" · 加时赛" if 得分.get("et") else "")
        # 未来赛程按日期由近及远，然后展示最近结束的比赛。
        排序键 = [0, (比赛日期 - 今天).days] if 比赛日期 >= 今天 else [1, (今天 - 比赛日期).days]
        文章.append({
            # ID 使用数据源原值，显示名称由中文映射调整时不会制造重复文章。
            "id": 稳定ID(序号, 日期文本, 原主队, 原客队),
            "标题": f"{主队} {比分} {客队}",
            "摘要": f"{阶段}{赛制说明} · {时间说明} · {场地} · {状态}",
            "来源": "openfootball/worldcup.json", "分类": "世界杯", "日期": 比赛日期.isoformat(),
            "链接": "https://github.com/openfootball/worldcup.json/tree/master/2026",
            "图片": 栏目封面["世界杯"], "封面": 栏目封面["世界杯"],
            "标签": [阶段, 状态], "比赛状态": 状态, "_排序": 排序键,
        })
    文章.sort(key=lambda x: x.get("_排序", [9, 0]))
    for 条目 in 文章:
        条目.pop("_排序", None)
    return 文章[:35]


def 采集世界杯新闻():
    """从公共 RSS 采集世界杯相关新闻、分析与评论；与比赛数据互补。"""
    地址列表 = [
        "https://news.google.com/rss/search?q=World+Cup+2026&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=2026%E4%B8%96%E7%95%8C%E6%9D%AF&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    ]
    旧索引 = 旧文章索引("世界杯.json")
    全部文章 = []
    for 地址 in 地址列表:
        try:
            响应 = requests.get(地址, headers=请求头, timeout=超时)
            响应.raise_for_status()
            feed = feedparser.parse(响应.content)
            for 条目 in feed.entries[:15]:
                原标题 = 清理文本(条目.get("title"), 150)
                链接 = 安全链接(条目.get("link"))
                if not 原标题 or not 链接:
                    continue
                摘要 = 清理文本(条目.get("summary") or 条目.get("description"), 220)
                日期 = 规范日期(条目.get("published") or 条目.get("updated"))
                文章ID = 稳定ID(原标题, 链接)
                临时项 = {"id": 文章ID, "链接": 链接}
                旧项 = 匹配旧文章(旧索引, 临时项)
                标题 = 生成中文标题(原标题, "世界杯", 旧项, "世界杯新闻")
                全部文章.append({
                    "id": 文章ID, "标题": 标题,
                    "原标题": 原标题,
                    "标题翻译方式": "DeepSeek" if ("世界杯", 原标题) in 深度求索已翻译标题 else ((旧项 or {}).get("标题翻译方式") or "短译/历史复用"),
                    "摘要": 摘要,
                    "来源": "Google News · World Cup 2026", "分类": "世界杯",
                    "日期": 日期, "链接": 链接,
                    "标签": ["世界杯", "足球", "新闻"],
                    "图片": 栏目封面["世界杯"], "封面": 栏目封面["世界杯"],
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"[提示] 世界杯新闻 RSS 采集失败：{e}")
            continue
    全部文章.sort(key=lambda x: x.get("日期", ""), reverse=True)
    return 全部文章[:25]


def 采集世界杯():
    旧索引 = 旧文章索引("世界杯.json")
    令牌 = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()

    # 1. 采集比赛数据
    if not 令牌:
        比赛文章 = 采集OpenFootball世界杯()
        数据源 = "openfootball/worldcup.json"
        数据源说明 = "2026 世界杯赛程与赛果；开放数据，无需密钥。"
        额外信息 = "当前使用公共领域开放数据；配置 FOOTBALL_DATA_TOKEN 后将自动切换到 football-data.org。"
    else:
        响应 = requests.get(
            "https://api.football-data.org/v4/competitions/WC/matches",
            headers={**请求头, "X-Auth-Token": 令牌}, timeout=超时,
        )
        响应.raise_for_status()
        比赛文章 = []
        for 比赛 in 响应.json().get("matches", []):
            主队 = 世界杯席位中文(比赛.get("homeTeam", {}).get("name"), {})
            客队 = 世界杯席位中文(比赛.get("awayTeam", {}).get("name"), {})
            状态 = 比赛.get("status", "SCHEDULED")
            全场 = 比赛.get("score", {}).get("fullTime", {})
            有比分 = 全场.get("home") is not None and 全场.get("away") is not None
            比分 = f"{全场.get('home')} : {全场.get('away')}" if 有比分 else "未开赛"
            开球 = 比赛.get("utcDate", "")
            try:
                时间 = datetime.fromisoformat(开球.replace("Z", "+00:00")).astimezone()
                日期, 本地时间 = 时间.strftime("%Y-%m-%d"), 时间.strftime("%m月%d日 %H:%M")
            except ValueError:
                日期, 本地时间 = 规范日期(开球), 开球
            阶段 = 比赛阶段中文(比赛.get("stage"))
            标题 = f"{主队} {比分} {客队}" if 有比分 else f"{主队} vs {客队}"
            try:
                排序时间 = datetime.fromisoformat(开球.replace("Z", "+00:00")).timestamp()
            except ValueError:
                排序时间 = 0
            直播状态 = {"IN_PLAY", "PAUSED", "LIVE", "EXTRA_TIME", "PENALTY_SHOOTOUT"}
            if 状态 in 直播状态:
                排序键 = [0, 排序时间]
            elif 状态 in {"SCHEDULED", "TIMED"}:
                排序键 = [1, 排序时间]
            else:
                排序键 = [2, -排序时间]
            比赛文章.append({
                "id": 稳定ID(比赛.get("id"), 标题), "标题": 标题,
                "摘要": f"{阶段} · 北京时间 {本地时间} · 状态 {状态}",
                "来源": "football-data.org", "分类": "世界杯", "日期": 日期,
                "链接": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",
                "图片": 栏目封面["世界杯"], "封面": 栏目封面["世界杯"],
                "标签": [阶段, 状态], "比赛状态": 状态, "开球时间": 开球,
                "_排序": 排序键,
            })
        比赛文章.sort(key=lambda x: x.get("_排序", [9, 0]))
        for 条目 in 比赛文章:
            条目.pop("_排序", None)
        数据源 = "football-data.org"
        数据源说明 = "2026 世界杯赛程、比分与对阵数据。"
        额外信息 = ""

    # 2. 采集世界杯新闻并合并
    新闻文章 = 采集世界杯新闻()
    文章 = 合并去重(新闻文章, 比赛文章, 最大条数=60)

    # 3. 补充杂志字段
    for 项 in 文章:
        补充杂志字段(项, 项.get("摘要", ""), 匹配旧文章(旧索引, 项))

    return 栏目数据("世界杯", 数据源, 数据源说明, 文章, "ok", 额外信息)


def 采集人文艺术():
    主题列表 = ["love", "solitude", "landscape", "family", "music", "poetry", "portrait"]
    # 按自然周轮换，避免每天新增一批图片导致仓库膨胀。
    随机 = random.Random(datetime.now().strftime("%G-W%V"))
    主题 = 随机.sample(主题列表, 2)
    候选ID = []
    for 关键词 in 主题:
        响应 = requests.get(
            "https://collectionapi.metmuseum.org/public/collection/v1/search",
            params={"hasImages": "true", "q": 关键词}, headers=请求头, timeout=超时,
        )
        响应.raise_for_status()
        候选ID.extend((响应.json().get("objectIDs") or [])[:30])
    随机.shuffle(候选ID)
    文章 = []
    旧索引 = 旧文章索引("人文艺术.json")
    本轮缓存 = []
    for 作品ID in 候选ID:
        if len(文章) >= 6:
            break
        try:
            响应 = requests.get(
                f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{作品ID}",
                headers=请求头, timeout=超时,
            )
            响应.raise_for_status()
            作品 = 响应.json()
        except Exception:
            continue
        if not 作品.get("isPublicDomain") or not 作品.get("primaryImageSmall"):
            continue
        原标题 = 清理文本(作品.get("title"), 150) or "未命名作品"
        作者 = 清理文本(作品.get("artistDisplayName"), 100) or "佚名"
        年代 = 清理文本(作品.get("objectDate"), 80) or "年代不详"
        材质 = 清理文本(作品.get("medium"), 100)
        原图链接 = 安全链接(作品.get("primaryImageSmall"))
        本地图 = 下载馆藏图片(原图链接, 作品ID)
        临时项 = {
            "id": 稳定ID(作品ID, 原标题),
            "链接": 安全链接(作品.get("objectURL")),
        }
        旧项 = 匹配旧文章(旧索引, 临时项)
        标题 = 生成中文标题(原标题, "人文艺术", 旧项, f"馆藏作品｜{作者}")
        项 = {
            "id": 临时项["id"], "标题": 标题,
            "原标题": 原标题,
            "标题翻译方式": "DeepSeek" if ("人文艺术", 原标题) in 深度求索已翻译标题 else ((旧项 or {}).get("标题翻译方式") or "保守规则/历史复用"),
            "摘要": f"{作者} · {年代}" + (f" · {材质}" if 材质 else ""),
            "来源": "The Metropolitan Museum of Art", "分类": "人文艺术",
            "日期": datetime.now().strftime("%Y-%m-%d"),
            "链接": 临时项["链接"],
            "图片": 本地图 or 栏目封面["人文艺术"],
            "原始图片": 原图链接,
            "封面": 本地图 or 栏目封面["人文艺术"],
            "版权": "Public Domain / Open Access", "标签": [主题[0], "公共领域"],
        }
        补充杂志字段(项, f"作者：{作者}；年代：{年代}；材质：{材质}", 旧项)
        文章.append(项)
        if 本地图:
            本轮缓存.append(本地图)
        time.sleep(0.08)
    清理馆藏缓存(本轮缓存)
    # 从其他开放馆藏补充
    已有链接 = {x.get("链接") for x in 文章}
    try:
        rijks文章 = 采集Rijksmuseum()
        for 项 in rijks文章:
            if len(文章) >= 14 or 项.get("链接") in 已有链接:
                continue
            已有链接.add(项.get("链接"))
            文章.append(项)
    except Exception as e:
        print(f"[提示] Rijksmuseum 采集失败：{e}")
    try:
        chicago文章 = 采集芝加哥艺术()
        for 项 in chicago文章:
            if len(文章) >= 14 or 项.get("链接") in 已有链接:
                continue
            已有链接.add(项.get("链接"))
            文章.append(项)
    except Exception as e:
        print(f"[提示] 芝加哥艺术博物馆采集失败：{e}")
    if not 文章:
        raise RuntimeError("没有获取到人文艺术数据")
    return 栏目数据(
        "人文艺术", "The Metropolitan Museum of Art / Rijksmuseum / Art Institute of Chicago",
        "每日从多个开放馆藏中选取艺术作品，图片可开放使用。", 文章,
    )


def 采集Rijksmuseum():
    """采集荷兰国立博物馆（Rijksmuseum）公共领域作品。"""
    密钥 = os.environ.get("RUKSMUSEUM_API_KEY", "")
    主题列表 = ["portrait", "landscape", "daily+life", "love", "family"]
    随机 = random.Random(datetime.now().strftime("%G-W%V"))
    主题 = 随机.sample(主题列表, 1)[0]
    文章 = []
    旧索引 = 旧文章索引("人文艺术.json")
    本轮缓存 = []
    try:
        搜索响应 = requests.get(
            "https://www.rijksmuseum.nl/api/en/collection",
            params={
                "key": 密钥, "ps": 20, "imgonly": "true",
                "hasimage": "true", "toppieces": "true",
                "culture": "en", "type": "painting", "q": 主题,
            },
            headers=请求头, timeout=超时,
        )
        搜索响应.raise_for_status()
        数据 = 搜索响应.json()
    except Exception as e:
        print(f"[提示] Rijksmuseum 搜索失败：{e}")
        return []
    作品列表 = (数据.get("artObjects") or [])[:20]
    for 作品 in 作品列表:
        if len(文章) >= 7:
            break
        对象号 = 作品.get("objectNumber")
        if not 对象号:
            continue
        try:
            详情响应 = requests.get(
                f"https://www.rijksmuseum.nl/api/en/collection/{对象号}",
                params={"key": 密钥, "culture": "en"},
                headers=请求头, timeout=超时,
            )
            详情响应.raise_for_status()
            详情 = 详情响应.json().get("artObject", {})
        except Exception as e:
            print(f"[提示] Rijksmuseum 作品 {对象号} 详情获取失败：{e}")
            continue
        图片信息 = 详情.get("webImage") or {}
        原图链接 = 安全链接(图片信息.get("url"))
        if not 原图链接:
            continue
        原标题 = 清理文本(详情.get("title"), 150) or "未命名作品"
        作者 = 清理文本(详情.get("principalMaker"), 100) or "佚名"
        年代 = 清理文本(详情.get("dating", {}).get("presentingDate"), 80) or "年代不详"
        本地图 = 下载Rijksmuseum图片(原图链接, 对象号)
        临时项 = {
            "id": 稳定ID("rijks", 对象号, 原标题),
            "链接": f"https://www.rijksmuseum.nl/en/collection/{对象号}",
        }
        旧项 = 匹配旧文章(旧索引, 临时项)
        标题 = 生成中文标题(原标题, "人文艺术", 旧项, f"馆藏作品｜{作者}")
        项 = {
            "id": 临时项["id"], "标题": 标题,
            "原标题": 原标题,
            "标题翻译方式": "DeepSeek" if ("人文艺术", 原标题) in 深度求索已翻译标题 else ((旧项 or {}).get("标题翻译方式") or "保守规则/历史复用"),
            "摘要": f"{作者} · {年代}",
            "来源": "Rijksmuseum", "分类": "人文艺术",
            "日期": datetime.now().strftime("%Y-%m-%d"),
            "链接": 临时项["链接"],
            "图片": 本地图 or 栏目封面["人文艺术"],
            "原始图片": 原图链接,
            "封面": 本地图 or 栏目封面["人文艺术"],
            "版权": "Public Domain", "标签": ["公共领域", "荷兰国立博物馆"],
        }
        补充杂志字段(项, f"作者：{作者}；年代：{年代}", 旧项)
        文章.append(项)
        if 本地图:
            本轮缓存.append(本地图)
        time.sleep(0.1)
    清理馆藏缓存(本轮缓存)
    return 文章


def 采集芝加哥艺术():
    """采集芝加哥艺术博物馆（Art Institute of Chicago）CC0 作品。"""
    主题列表 = ["landscape", "portrait", "still+life", "love", "music"]
    随机 = random.Random(datetime.now().strftime("%G-W%V"))
    主题 = 随机.sample(主题列表, 1)[0]
    文章 = []
    旧索引 = 旧文章索引("人文艺术.json")
    本轮缓存 = []
    try:
        搜索响应 = requests.get(
            "https://api.artic.edu/api/v1/artworks/search",
            params={
                "q": 主题, "limit": 20,
                "fields": "id,title,artist_display,date_display,image_id,api_link,style_title,medium_display",
            },
            headers=请求头, timeout=超时,
        )
        搜索响应.raise_for_status()
        数据 = 搜索响应.json()
    except Exception as e:
        print(f"[提示] 芝加哥艺术博物馆搜索失败：{e}")
        return []
    作品列表 = (数据.get("data") or [])[:20]
    for 作品 in 作品列表:
        if len(文章) >= 7:
            break
        图片ID = 作品.get("image_id")
        作品ID = 作品.get("id")
        if not 图片ID or not 作品ID:
            continue
        原标题 = 清理文本(作品.get("title"), 150) or "未命名作品"
        作者 = 清理文本(作品.get("artist_display"), 100) or "佚名"
        年代 = 清理文本(作品.get("date_display"), 80) or "年代不详"
        材质 = 清理文本(作品.get("medium_display"), 100)
        原图链接 = f"https://www.artic.edu/iiif/2/{图片ID}/full/843,/0/default.jpg"
        本地图 = 下载芝加哥图片(原图链接, 作品ID)
        临时项 = {
            "id": 稳定ID("aic", 作品ID, 原标题),
            "链接": f"https://www.artic.edu/artworks/{作品ID}",
        }
        旧项 = 匹配旧文章(旧索引, 临时项)
        标题 = 生成中文标题(原标题, "人文艺术", 旧项, f"馆藏作品｜{作者}")
        项 = {
            "id": 临时项["id"], "标题": 标题,
            "原标题": 原标题,
            "标题翻译方式": "DeepSeek" if ("人文艺术", 原标题) in 深度求索已翻译标题 else ((旧项 or {}).get("标题翻译方式") or "保守规则/历史复用"),
            "摘要": f"{作者} · {年代}" + (f" · {材质}" if 材质 else ""),
            "来源": "Art Institute of Chicago", "分类": "人文艺术",
            "日期": datetime.now().strftime("%Y-%m-%d"),
            "链接": 临时项["链接"],
            "图片": 本地图 or 栏目封面["人文艺术"],
            "原始图片": 原图链接,
            "封面": 本地图 or 栏目封面["人文艺术"],
            "版权": "CC0 / Public Domain", "标签": ["公共领域", "芝加哥艺术博物馆"],
        }
        补充杂志字段(项, f"作者：{作者}；年代：{年代}；材质：{材质}", 旧项)
        文章.append(项)
        if 本地图:
            本轮缓存.append(本地图)
        time.sleep(0.1)
    清理馆藏缓存(本轮缓存)
    return 文章


def 提取PubMed文本(元素, 路径):
    节点 = 元素.find(路径)
    return "".join(节点.itertext()).strip() if 节点 is not None else ""


def _解析PubMed日期(记录):
    """从 PubMed XML 记录中提取日期；优先完整日期，其次仅年份，绝不编造月日。"""
    月名映射 = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    年 = 提取PubMed文本(记录, ".//PubDate/Year")
    月文本 = 提取PubMed文本(记录, ".//PubDate/Month")
    日文本 = 提取PubMed文本(记录, ".//PubDate/Day")

    月 = None
    if 月文本:
        小写 = 月文本.strip().lower().rstrip(".")
        try:
            月 = int(小写)
        except ValueError:
            月 = 月名映射.get(小写)
        if 月 is not None and not (1 <= 月 <= 12):
            月 = None

    日 = None
    if 日文本 and 月 is not None:
        try:
            日 = int(日文本.strip())
        except ValueError:
            pass

    # 完整日期：年月日齐全且合法
    if 年 and 月 is not None and 日 is not None:
        try:
            datetime(int(年), 月, 日)
            return f"{年}-{月:02d}-{日:02d}"
        except ValueError:
            pass

    # 仅年月：月份合法
    if 年 and 月 is not None:
        return f"{年}-{月:02d}"

    # 仅年份
    if 年:
        return 年

    # 从 MedlineDate（如 "2025 Jan-Feb"）中尝试提取年份
    原始日期 = 提取PubMed文本(记录, ".//PubDate/MedlineDate")
    if 原始日期:
        年匹配 = re.search(r"(20\d{2})", 原始日期)
        if 年匹配:
            return 年匹配.group(1)

    return datetime.now().strftime("%Y-%m-%d")


def 采集情感新闻():
    """从 Google News RSS 采集情感、心理、人际关系相关新闻。"""
    地址列表 = [
        "https://news.google.com/rss/search?q=emotion+psychology+relationship&hl=en-US&gl=US&ceid=US:en",
        "https://news.google.com/rss/search?q=%E6%83%85%E7%BB%AA+%E5%BF%83%E7%90%86+%E4%BA%BA%E9%99%85%E5%85%B3%E7%B3%BB&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    ]
    旧索引 = 旧文章索引("情感.json")
    全部文章 = []
    for 地址 in 地址列表:
        try:
            响应 = requests.get(地址, headers=请求头, timeout=超时)
            响应.raise_for_status()
            feed = feedparser.parse(响应.content)
            for 条目 in feed.entries[:10]:
                原标题 = 清理文本(条目.get("title"), 150)
                链接 = 安全链接(条目.get("link"))
                if not 原标题 or not 链接:
                    continue
                摘要 = 清理文本(条目.get("summary") or 条目.get("description"), 220)
                日期 = 规范日期(条目.get("published") or 条目.get("updated"))
                文章ID = 稳定ID(原标题, 链接)
                临时项 = {"id": 文章ID, "链接": 链接}
                旧项 = 匹配旧文章(旧索引, 临时项)
                标题 = 生成中文标题(原标题, "情感", 旧项, "情感心理新闻")
                全部文章.append({
                    "id": 文章ID, "标题": 标题,
                    "原标题": 原标题,
                    "标题翻译方式": "DeepSeek" if ("情感", 原标题) in 深度求索已翻译标题 else ((旧项 or {}).get("标题翻译方式") or "短译/历史复用"),
                    "摘要": 摘要,
                    "来源": "Google News · 情感心理", "分类": "情感",
                    "日期": 日期, "链接": 链接,
                    "标签": ["情感", "心理", "新闻"],
                    "图片": 栏目封面["情感"], "封面": 栏目封面["情感"],
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"[提示] 情感新闻 RSS 采集失败：{e}")
            continue
    全部文章.sort(key=lambda x: x.get("日期", ""), reverse=True)
    return 全部文章[:15]


def 采集情感():
    """从 PubMed 和 Google News 采集情感、关系、心理相关文章。"""
    当前年 = datetime.now().year
    查询 = (
        '(("emotion regulation"[Title] OR loneliness[Title] OR attachment[Title] '
        'OR "close relationship"[Title] OR "romantic relationship"[Title] '
        'OR "social connection"[Title]) '
        f'AND 2025:{当前年}[pdat])'
    )
    搜索 = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "pubmed", "term": 查询, "retmode": "json", "retmax": 18, "sort": "pub date"},
        headers=请求头, timeout=超时,
    )
    搜索.raise_for_status()
    ids = 搜索.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        raise RuntimeError("PubMed 没有返回情感研究")
    详情 = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
        params={"db": "pubmed", "id": ",".join(ids), "retmode": "xml"},
        headers=请求头, timeout=超时,
    )
    详情.raise_for_status()
    根 = ET.fromstring(详情.content)

    旧索引 = 旧文章索引("情感.json")
    pubmed文章 = []
    for 记录 in 根.findall(".//PubmedArticle"):
        pmid = 提取PubMed文本(记录, ".//PMID")
        原标题 = 提取PubMed文本(记录, ".//ArticleTitle")
        if not pmid or not 原标题:
            continue
        标题小写 = 原标题.lower()
        if "attachment" in 标题小写 and any(
            词 in 标题小写 for 词 in ("antibody", "virus", "viral", "adhesion", "fusion", "protein", "receptor", "membrane")
        ):
            continue
        期刊 = 提取PubMed文本(记录, ".//Journal/Title") or "PubMed"
        日期 = _解析PubMed日期(记录)
        关键词 = [清理文本("".join(k.itertext()), 40) for k in 记录.findall(".//Keyword")[:3]]
        摘要段 = [清理文本("".join(a.itertext()), 800) for a in 记录.findall(".//Abstract/AbstractText")]
        论文摘要 = 清理文本(" ".join(x for x in 摘要段 if x), 1600)
        临时项 = {
            "id": 稳定ID(pmid, 原标题),
            "链接": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }
        旧项 = 匹配旧文章(旧索引, 临时项)
        标题 = 生成中文标题(原标题, "情感", 旧项, "关系与情绪研究")
        pubmed文章.append({
            "id": 临时项["id"], "标题": 标题,
            "原标题": 原标题,
            "标题翻译方式": "DeepSeek" if ("情感", 原标题) in 深度求索已翻译标题 else ((旧项 or {}).get("标题翻译方式") or "短译/历史复用"),
            "摘要": f"来自《{期刊}》的关系与情绪研究。仅作知识阅读，不构成医疗建议。",
            "来源": f"PubMed · {期刊}", "分类": "情感", "日期": 日期,
            "链接": 临时项["链接"],
            "标签": [x for x in 关键词 if x][:3] or ["情绪", "关系"],
            # PubMed 元数据不提供论文主图，不抓取出版社页面；明确回退到栏目封面。
            "图片": 栏目封面["情感"], "封面": 栏目封面["情感"],
            "_论文素材": 论文摘要 or 原标题,
        })
        if len(pubmed文章) >= 12:
            break
        time.sleep(0.08)

    新闻文章 = 采集情感新闻()
    文章 = 合并去重(新闻文章, pubmed文章, 最大条数=25)

    for 项 in 文章:
        素材 = 项.pop("_论文素材", None) or 项.get("摘要", "")
        补充杂志字段(项, 素材, 匹配旧文章(旧索引, 项))

    return 栏目数据(
        "情感", "PubMed / NCBI · Google News",
        "从关系、孤独、依恋与情绪研究中寻找可靠线索；不是医疗建议。", 文章,
    )


def 安全执行(文件名, 采集函数):
    try:
        数据 = 采集函数()
        原子保存(文件名, 数据)
        return True
    except Exception as e:
        print(f"[失败] {文件名}：{e}")
        旧数据 = 读取旧数据(文件名)
        if 旧数据.get("articles"):
            旧数据["status"] = "stale"
            旧数据["message"] = f"本轮更新失败，当前展示上次成功数据：{e}"
            原子保存(文件名, 旧数据)
        return False


def 主流程():
    print("=" * 60)
    print("极光引擎 · 综合栏目自动采集")
    print(f"运行时间：{现在字符串()}")
    print("=" * 60)
    任务 = [
        ("国际形势.json", 采集国际形势),
        ("世界杯.json", 采集世界杯),
        ("人文艺术.json", 采集人文艺术),
        ("情感.json", 采集情感),
    ]
    成功 = sum(安全执行(文件名, 函数) for 文件名, 函数 in 任务)
    print(f"[完成] {成功}/{len(任务)} 个栏目已更新")
    return 0 if 成功 else 1


if __name__ == "__main__":
    raise SystemExit(主流程())
