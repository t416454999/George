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
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import feedparser
import requests


根目录 = Path(__file__).resolve().parent
请求头 = {
    "User-Agent": "AuroraEngine/1.0 (+https://boke.jgyq.me)",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
}
超时 = 30


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


def 采集联合国中文新闻():
    地址 = "https://news.un.org/feed/subscribe/zh/news/all/rss.xml"
    响应 = requests.get(地址, headers=请求头, timeout=超时)
    响应.raise_for_status()
    feed = feedparser.parse(响应.content)
    文章 = []
    for 条目 in feed.entries[:24]:
        标题 = 清理文本(条目.get("title"), 150)
        链接 = 安全链接(条目.get("link"))
        if not 标题 or not 链接:
            continue
        摘要 = 清理文本(条目.get("summary") or 条目.get("description"), 220)
        日期 = 规范日期(条目.get("published") or 条目.get("updated"))
        文章.append({
            "id": 稳定ID(标题, 链接), "标题": 标题, "摘要": 摘要,
            "来源": "联合国新闻", "分类": "国际形势", "日期": 日期,
            "链接": 链接, "标签": ["国际", "联合国"],
        })
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
    for 条目 in 响应.json().get("articles", []):
        原标题 = 清理文本(条目.get("title"), 160)
        链接 = 安全链接(条目.get("url"))
        if not 原标题 or not 链接:
            continue
        标题 = 翻译成中文(原标题)
        域名 = 清理文本(条目.get("domain"), 80) or urlparse(链接).netloc
        文章.append({
            "id": 稳定ID(原标题, 链接), "标题": 标题,
            "原标题": 原标题 if 标题 != 原标题 else "",
            "摘要": f"全球新闻索引收录的 {域名} 最新报道，点击阅读原文。",
            "来源": 域名 or "GDELT", "分类": "国际形势",
            "日期": 规范日期(条目.get("seendate")), "链接": 链接,
            "标签": ["国际", "全球媒体"],
        })
    return 文章


def 采集国际形势():
    旧文章 = 读取旧数据("国际形势.json").get("articles", [])
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


def 采集OpenFootball世界杯():
    地址 = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
    响应 = requests.get(地址, headers=请求头, timeout=超时)
    响应.raise_for_status()
    今天 = datetime.now().date()
    文章 = []
    for 序号, 比赛 in enumerate(响应.json().get("matches", []), 1):
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
        主队, 客队 = 比赛.get("team1") or "待定", 比赛.get("team2") or "待定"
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
            "id": 稳定ID(序号, 日期文本, 主队, 客队),
            "标题": f"{主队} {比分} {客队}",
            "摘要": f"{阶段}{赛制说明} · {时间说明} · {场地} · {状态}",
            "来源": "openfootball/worldcup.json", "分类": "世界杯", "日期": 比赛日期.isoformat(),
            "链接": "https://github.com/openfootball/worldcup.json/tree/master/2026",
            "标签": [阶段, 状态], "比赛状态": 状态, "_排序": 排序键,
        })
    文章.sort(key=lambda x: x.get("_排序", [9, 0]))
    for 条目 in 文章:
        条目.pop("_排序", None)
    return 文章[:60]


def 采集世界杯():
    令牌 = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    if not 令牌:
        文章 = 采集OpenFootball世界杯()
        return 栏目数据(
            "世界杯", "openfootball/worldcup.json",
            "2026 世界杯赛程与赛果；开放数据，无需密钥。", 文章,
            "ok", "当前使用公共领域开放数据；配置 FOOTBALL_DATA_TOKEN 后将自动切换到 football-data.org。",
        )
    响应 = requests.get(
        "https://api.football-data.org/v4/competitions/WC/matches",
        headers={**请求头, "X-Auth-Token": 令牌}, timeout=超时,
    )
    响应.raise_for_status()
    文章 = []
    for 比赛 in 响应.json().get("matches", []):
        主队 = 比赛.get("homeTeam", {}).get("name") or "待定"
        客队 = 比赛.get("awayTeam", {}).get("name") or "待定"
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
        文章.append({
            "id": 稳定ID(比赛.get("id"), 标题), "标题": 标题,
            "摘要": f"{阶段} · 北京时间 {本地时间} · 状态 {状态}",
            "来源": "football-data.org", "分类": "世界杯", "日期": 日期,
            "链接": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026",
            "标签": [阶段, 状态], "比赛状态": 状态, "开球时间": 开球,
            "_排序": 排序键,
        })
    文章.sort(key=lambda x: x.get("_排序", [9, 0]))
    for 条目 in 文章:
        条目.pop("_排序", None)
    return 栏目数据("世界杯", "football-data.org", "2026 世界杯赛程、比分与对阵数据。", 文章[:60])


def 采集人文艺术():
    主题列表 = ["love", "solitude", "landscape", "family", "music", "poetry", "portrait"]
    随机 = random.Random(datetime.now().strftime("%Y-%m-%d"))
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
    for 作品ID in 候选ID:
        if len(文章) >= 14:
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
        标题 = 翻译成中文(原标题)
        作者 = 清理文本(作品.get("artistDisplayName"), 100) or "佚名"
        年代 = 清理文本(作品.get("objectDate"), 80) or "年代不详"
        材质 = 清理文本(作品.get("medium"), 100)
        文章.append({
            "id": 稳定ID(作品ID, 原标题), "标题": 标题,
            "原标题": 原标题 if 标题 != 原标题 else "",
            "摘要": f"{作者} · {年代}" + (f" · {材质}" if 材质 else ""),
            "来源": "The Metropolitan Museum of Art", "分类": "人文艺术",
            "日期": datetime.now().strftime("%Y-%m-%d"),
            "链接": 安全链接(作品.get("objectURL")),
            "图片": 安全链接(作品.get("primaryImageSmall")),
            "版权": "Public Domain / Open Access", "标签": [主题[0], "公共领域"],
        })
        time.sleep(0.08)
    if not 文章:
        raise RuntimeError("The Met 没有返回可用的公共领域作品")
    return 栏目数据(
        "人文艺术", "The Metropolitan Museum of Art Open Access",
        "每日从公共领域馆藏中选取艺术作品，图片可开放使用。", 文章,
    )


def 提取PubMed文本(元素, 路径):
    节点 = 元素.find(路径)
    return "".join(节点.itertext()).strip() if 节点 is not None else ""


def 采集情感():
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
    文章 = []
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
        标题 = 翻译成中文(原标题)
        期刊 = 提取PubMed文本(记录, ".//Journal/Title") or "PubMed"
        年 = 提取PubMed文本(记录, ".//PubDate/Year")
        月 = 提取PubMed文本(记录, ".//PubDate/Month")
        日期 = f"{年}-01-01" if 年 else datetime.now().strftime("%Y-%m-%d")
        关键词 = [清理文本("".join(k.itertext()), 40) for k in 记录.findall(".//Keyword")[:3]]
        文章.append({
            "id": 稳定ID(pmid, 原标题), "标题": 标题,
            "原标题": 原标题 if 标题 != 原标题 else "",
            "摘要": f"来自《{期刊}》的关系与情绪研究。仅作知识阅读，不构成医疗建议。",
            "来源": f"PubMed · {期刊}", "分类": "情感", "日期": 日期,
            "链接": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "标签": [x for x in 关键词 if x][:3] or ["情绪", "关系"],
        })
        time.sleep(0.08)
    return 栏目数据(
        "情感", "PubMed / NCBI",
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
