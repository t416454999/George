#!/usr/bin/env python3
"""在 GitHub Actions 云端按编辑规则生成“全部”与首页推荐。"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


根目录 = Path(__file__).resolve().parent
规则版本 = "editorial-v1.0"
北京时间 = timezone(timedelta(hours=8))
云端运行 = os.environ.get("GITHUB_ACTIONS") == "true" or os.environ.get("AURORA_CLOUD_RUNTIME") == "github-actions"

一手来源 = {
    "OpenAI 官方", "Anthropic 官方", "Google DeepMind 官方", "Hugging Face 官方",
    "GitHub 官方博客", "arXiv AI", "联合国新闻", "The Metropolitan Museum of Art",
}
专业来源 = {"36氪", "量子位", "雷锋网", "新浪科技"}
AI关键词 = re.compile(
    r"AI|人工智能|大模型|模型|智能体|机器人|机器学习|深度学习|算力|芯片|开源|"
    r"OpenAI|Anthropic|Claude|Gemini|DeepMind|GPT|LLM|Agent|Transformer|推理",
    re.I,
)
占位符 = re.compile(r"\b(?:[WLT]\d{1,3}|TBD|TBA)\b|待定席位|胜者|负者", re.I)
标题党 = re.compile(r"震惊|炸裂|疯了|必看|史诗级|深V|暴涨|暴跌|千亿|重磅突发", re.I)


def 读取JSON(文件名, 默认):
    try:
        return json.loads((根目录 / 文件名).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 默认


def 文章集合():
    结果 = []
    AI文章 = 读取JSON("文章数据库.json", [])
    for 文章 in AI文章 if isinstance(AI文章, list) else []:
        项 = dict(文章)
        项["候选栏目"] = "AI"
        结果.append(项)
    for 文件名 in ("国际形势.json", "世界杯.json", "人文艺术.json", "情感.json"):
        数据 = 读取JSON(文件名, {})
        for 文章 in 数据.get("articles", []) if isinstance(数据, dict) else []:
            项 = dict(文章)
            项["候选栏目"] = 项.get("分类") or 文件名.removesuffix(".json")
            项["栏目状态"] = 数据.get("status", "ok")
            结果.append(项)
    return 结果


def 解析日期(值):
    文本 = str(值 or "").strip()
    if not 文本:
        return None
    # YYYY-MM-DD
    if len(文本) >= 10:
        try:
            return datetime.strptime(文本[:10], "%Y-%m-%d").replace(tzinfo=北京时间)
        except ValueError:
            pass
    # YYYY（仅年份）
    if len(文本) == 4 and 文本.isdigit():
        try:
            return datetime.strptime(文本, "%Y").replace(tzinfo=北京时间)
        except ValueError:
            pass
    return None


def 来源等级(文章):
    来源 = str(文章.get("来源", ""))
    if 来源 in 一手来源 or 来源.startswith("PubMed ·"):
        return "A", 25
    if 来源 in 专业来源 or 来源 == "openfootball/worldcup.json":
        return "B", 17
    return "C", 8


def 硬门槛(文章, 现在, 否决集合):
    ID = str(文章.get("id", ""))
    标题 = str(文章.get("标题", "")).strip()
    摘要 = str(文章.get("摘要") or 文章.get("导语") or "").strip()
    if ID in 否决集合:
        return "manual_veto"
    if not ID or not 标题 or not 摘要 or not str(文章.get("来源", "")).strip():
        return "missing_required_fields"
    if not re.match(r"^https?://", str(文章.get("链接") or 文章.get("原文链接") or "")):
        return "invalid_source_link"
    if 占位符.search(标题):
        return "unresolved_placeholder"
    if "�" in 标题 or re.search(r"(?:Ã|â€|ðŸ)", 标题):
        return "broken_translation"
    if 文章.get("栏目状态") in {"stale", "config_required"}:
        return "stale_section"
    日期 = 解析日期(文章.get("日期"))
    if not 日期:
        return "invalid_or_future_date"
    if 日期 > 现在:
        是24小时内世界杯 = 文章.get("分类") == "世界杯" and (日期 - 现在).total_seconds() <= 86400
        if not 是24小时内世界杯:
            return "invalid_or_future_date"
    if 文章.get("候选栏目") == "AI" and not AI关键词.search(标题 + " " + 摘要):
        return "off_topic"
    if 标题党.search(标题):
        return "sensational_title"
    if 文章.get("分类") == "世界杯" and 文章.get("比赛状态") == "未开赛":
        相差小时 = (日期 - 现在).total_seconds() / 3600
        if 相差小时 > 24:
            return "future_schedule"
    return ""


def 评分(文章, 现在):
    等级, 可信度 = 来源等级(文章)
    日期 = 解析日期(文章.get("日期")) or 现在
    天数 = max(0, (现在 - 日期).total_seconds() / 86400)
    分类 = 文章.get("分类") or 文章.get("候选栏目")
    if 分类 == "人文艺术":
        时效 = 8
    elif 分类 == "情感":
        时效 = 12 if 天数 <= 180 else 6
    else:
        时效 = 20 if 天数 <= 1 else 14 if 天数 <= 2 else 8 if 天数 <= 3 else 2
    重要词 = re.compile(r"发布|推出|通过|达成|停火|决赛|半决赛|冠军|监管|安全|研究|联合国|全球|开源", re.I)
    公共价值 = 16 if 重要词.search(str(文章.get("标题", ""))) else 11
    可追溯 = 15 if 等级 == "A" else 10 if 等级 == "B" else 4
    完整度 = 10 if len(str(文章.get("摘要") or "")) >= 45 else 6
    图片 = str(文章.get("图片") or 文章.get("封面") or "")
    版权 = str(文章.get("版权") or "")
    是授权真实图 = (
        图片.startswith("assets/media/") and 文章.get("来源") == "联合国新闻"
    ) or (
        图片.startswith("assets/art/") and ("Public Domain" in 版权 or "Open Access" in 版权)
    )
    图片分 = 5 if 是授权真实图 else 0
    编辑价值 = 5 if 分类 in {"国际形势", "人文艺术", "情感", "世界杯"} or 等级 == "A" else 3
    扣分项 = []
    扣分 = 0
    if 等级 == "C":
        扣分 += 20; 扣分项.append("aggregator_or_unknown_source")
    总分 = max(0, 可信度 + 时效 + 公共价值 + 可追溯 + 完整度 + 图片分 + 编辑价值 - 扣分)
    return 总分, {
        "可信度": 可信度, "时效": 时效, "公共价值": 公共价值, "一手可追溯": 可追溯,
        "完整度": 完整度, "真实图片": 图片分, "编辑价值": 编辑价值, "扣分": -扣分,
    }, 等级, 扣分项


def 选择精选(候选, 人工, 现在):
    否决集合 = {str(x) for x in 人工.get("veto_ids", [])}
    合格, 拒绝 = [], []
    for 文章 in 候选:
        原因 = 硬门槛(文章, 现在, 否决集合)
        if 原因:
            拒绝.append({"id": 文章.get("id"), "reason": 原因})
            continue
        分数, 分项, 等级, 扣分项 = 评分(文章, 现在)
        if 分数 < 50:
            拒绝.append({"id": 文章.get("id"), "reason": "score_below_50", "score": 分数})
            continue
        项 = dict(文章)
        理由 = "可信来源、时效与公共价值达到推荐门槛"
        if 文章.get("分类") == "人文艺术":
            理由 = "公共领域馆藏，图像与出处完整"
        elif 文章.get("分类") == "情感":
            理由 = "原始研究可追溯，具有关系与情绪阅读价值"
        elif 文章.get("分类") == "世界杯":
            理由 = "球队已确认且处于重要比赛时间窗口"
        项.update({
            "编辑分": 分数, "评分分项": 分项, "来源级别": 等级, "扣分项": 扣分项,
            "入选理由": 理由, "规则版本": 规则版本,
        })
        合格.append(项)
    合格.sort(key=lambda x: (-x["编辑分"], str(x.get("日期", "")), str(x.get("id", ""))))

    # 同一标题只留最高分；首页前四限制同源、同栏目，并尽量覆盖至少三个栏目。
    去重, 见过标题 = [], set()
    for 项 in 合格:
        键 = re.sub(r"[^\w\u4e00-\u9fff]", "", str(项.get("标题", "")).lower())[:50]
        if 键 and 键 in 见过标题:
            拒绝.append({"id": 项.get("id"), "reason": "duplicate_title"})
            continue
        见过标题.add(键); 去重.append(项)

    def 有效人工项(配置):
        if not isinstance(配置, dict) or not all(配置.get(k) for k in ("id", "editor", "reason", "starts_at", "expires_at")):
            return False
        try:
            开始 = datetime.fromisoformat(str(配置["starts_at"]).replace("Z", "+00:00"))
            到期 = datetime.fromisoformat(str(配置["expires_at"]).replace("Z", "+00:00"))
            if 开始.tzinfo is None: 开始 = 开始.replace(tzinfo=北京时间)
            if 到期.tzinfo is None: 到期 = 到期.replace(tzinfo=北京时间)
            return 开始.astimezone(北京时间) <= 现在 < 到期.astimezone(北京时间)
        except ValueError:
            return False

    置顶 = 人工.get("pinned_headline") or {}
    置顶ID = str(置顶.get("id")) if 有效人工项(置顶) else ""
    置顶项 = next((x for x in 去重 if str(x.get("id")) == 置顶ID), None)
    头条候选 = [
        x for x in 去重
        if x["编辑分"] >= 78
        and x["评分分项"]["可信度"] >= 18
        and x["评分分项"]["公共价值"] >= 14
        and x["来源级别"] != "C"
        and x.get("分类") not in {"人文艺术", "情感"}
    ]
    头条 = 置顶项 or (头条候选[0] if 头条候选 else None)

    已选 = []
    if 头条:
        已选.append(头条)
    for 配置 in 人工.get("featured_ids", []):
        if len(已选) >= 4 or not 有效人工项(配置):
            continue
        人工精选 = next((x for x in 去重 if str(x.get("id")) == str(配置.get("id"))), None)
        if 人工精选 and 人工精选 not in 已选:
            已选.append(人工精选)
    栏目计数, 来源计数 = {}, {}
    for 项 in 已选:
        栏目计数[项.get("候选栏目")] = 1; 来源计数[项.get("来源")] = 1
    for 项 in 去重:
        if len(已选) >= 12 or 项 in 已选:
            continue
        栏目 = 项.get("候选栏目")
        上限 = 2 if 栏目 == "AI" else 1
        if len(已选) < 4 and (栏目计数.get(栏目, 0) >= 上限 or 来源计数.get(项.get("来源"), 0) >= 1):
            continue
        if len(已选) >= 4 and 栏目计数.get(栏目, 0) >= 3:
            continue
        已选.append(项)
        栏目计数[栏目] = 栏目计数.get(栏目, 0) + 1
        来源计数[项.get("来源")] = 来源计数.get(项.get("来源"), 0) + 1
    return 已选, 头条, 拒绝


def main():
    if not 云端运行:
        print("[跳过] 首页精选只由 GitHub Actions 云端生成")
        return
    现在 = datetime.now(北京时间)
    人工 = 读取JSON("首页人工编辑.json", {})
    精选, 头条, 拒绝 = 选择精选(文章集合(), 人工, 现在)
    输出 = {
        "generated": 现在.astimezone().isoformat(timespec="seconds"), "policy_version": 规则版本,
        "headline_id": 头条.get("id") if 头条 else None,
        "headline_reason": 头条.get("入选理由") if 头条 else "没有候选达到头条门槛",
        "count": len(精选), "articles": 精选,
        "audit": {
            "as_of": 现在.isoformat(timespec="seconds"), "candidate_count": len(文章集合()),
            "rejected_count": 0, "rejected": [],
        },
    }
    for 项 in 输出["articles"]:
        项["选入时间"] = 现在.isoformat(timespec="seconds")
    去重拒绝 = []
    已见拒绝 = set()
    for 项 in 拒绝:
        键 = (str(项.get("id")), 项.get("reason"), 项.get("score"))
        if 键 not in 已见拒绝:
            已见拒绝.add(键); 去重拒绝.append(项)
    输出["audit"]["rejected"] = 去重拒绝
    输出["audit"]["rejected_count"] = len(去重拒绝)
    临时 = 根目录 / "首页精选.json.tmp"
    临时.write_text(json.dumps(输出, ensure_ascii=False, indent=2), encoding="utf-8")
    临时.replace(根目录 / "首页精选.json")
    print(f"[保存] 首页精选.json：{len(精选)} 条；头条={输出['headline_id']}")


if __name__ == "__main__":
    main()
