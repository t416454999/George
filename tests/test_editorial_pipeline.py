import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


editor = load("aurora_editor", "生成首页精选.py")
collector = load("aurora_sections", "自动采集综合栏目.py")
ai = load("aurora_ai", "自动采集AI资讯.py")


class EditorialBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 14, 12, tzinfo=editor.北京时间)

    def article(self, ident, title, source="联合国新闻", category="国际形势", hours=1, **extra):
        item = {
            "id": ident, "标题": title, "摘要": extra.pop("摘要", "这是包含明确人物、事件、时间和影响的完整可靠摘要，便于读者理解事件。"),
            "来源": source, "分类": category, "候选栏目": category,
            "日期": (self.now - timedelta(hours=hours)).strftime("%Y-%m-%d"),
            "链接": f"https://example.com/{ident}",
        }
        item.update(extra)
        return item

    def select(self, items, manual=None):
        return editor.选择精选(items, manual or {}, self.now)

    def test_01_tier_c_visual_loses_to_tier_a(self):
        c = self.article("c", "全球重大安全研究发布", source="某聚合器", 图片="assets/art/x.webp")
        a = self.article("a", "联合国发布全球安全报告")
        chosen, headline, _ = self.select([c, a])
        self.assertEqual(headline["id"], "a")
        self.assertNotIn("c", [str(x["id"]) for x in chosen])

    def test_02_placeholder_world_cup_rejected(self):
        item = self.article("m", "L101 vs L102", source="openfootball/worldcup.json", category="世界杯")
        _, _, rejected = self.select([item])
        self.assertIn("unresolved_placeholder", [x["reason"] for x in rejected])

    def test_03_duplicate_prefers_primary(self):
        primary = self.article("p", "联合国发布人工智能安全报告")
        rewrite = self.article("r", "联合国正式发布AI安全报告", source="36氪")
        chosen, _, rejected = self.select([rewrite, primary])
        self.assertEqual([x["id"] for x in chosen], ["p"])
        self.assertIn("near_duplicate", [x["reason"] for x in rejected])

    def test_04_manual_rumor_cannot_bypass_gate(self):
        rumor = self.article("r", "网传重要政策即将发布")
        pin = {"id": "r", "editor": "test", "reason": "test", "starts_at": "2026-07-14T00:00:00+08:00", "expires_at": "2026-07-14T23:00:00+08:00"}
        _, headline, rejected = self.select([rumor], {"pinned_headline": pin})
        self.assertIsNone(headline)
        self.assertIn("rumor_or_unverified", [x["reason"] for x in rejected])

    def test_05_fresh_story_outranks_week_old_heat(self):
        fresh = self.article("fresh", "联合国发布安全研究")
        old = self.article("old", "联合国发布全球安全研究", hours=24 * 7, 热度=100)
        chosen, _, _ = self.select([old, fresh])
        self.assertEqual(chosen[0]["id"], "fresh")

    def test_06_art_can_feature_but_not_auto_headline(self):
        art = self.article("art", "馆藏作品", source="The Metropolitan Museum of Art", category="人文艺术", 图片="assets/art/x.webp", 版权="Public Domain")
        chosen, headline, _ = self.select([art])
        self.assertEqual(chosen[0]["id"], "art")
        self.assertIsNone(headline)

    def test_07_pubmed_without_image_can_feature(self):
        study = self.article("study", "关系与情绪调节研究发布", source="PubMed · Journal", category="情感")
        chosen, _, _ = self.select([study])
        self.assertEqual(chosen[0]["id"], "study")
        self.assertEqual(chosen[0]["评分分项"]["真实图片"], 0)

    def test_08_no_forced_headline_below_78(self):
        low = self.article("low", "普通行业动态", source="36氪", category="AI")
        _, headline, _ = self.select([low])
        self.assertIsNone(headline)

    def test_09_top_four_are_diverse(self):
        items = [self.article(f"ai{i}", f"OpenAI 发布第{i}项模型研究", source="OpenAI 官方", category="AI") for i in range(4)]
        items += [self.article("intl", "联合国发布全球安全报告"), self.article("art", "馆藏作品", source="The Metropolitan Museum of Art", category="人文艺术", 图片="assets/art/x.webp", 版权="Public Domain")]
        chosen, _, _ = self.select(items)
        self.assertGreaterEqual(len({x["候选栏目"] for x in chosen[:4]}), 3)
        self.assertLessEqual(sum(x["候选栏目"] == "AI" for x in chosen[:4]), 2)

    def test_10_order_is_deterministic_and_newer_wins_tie(self):
        newer = self.article("b", "联合国发布乙项安全报告", hours=1)
        older = self.article("a", "联合国发布甲项安全报告", hours=25)
        one = [x["id"] for x in self.select([older, newer])[0]]
        two = [x["id"] for x in self.select([older, newer])[0]]
        self.assertEqual(one, two)
        self.assertEqual(one[0], "b")

    def test_major_world_cup_window_reads_summary_and_exact_kickoff(self):
        match = self.article(
            "match", "加拿大 vs 日本", source="openfootball/worldcup.json", category="世界杯",
            摘要="世界杯半决赛，球队已经确认", 比赛状态="未开赛", 开球时间="2026-07-15T08:00:00+08:00",
        )
        self.assertTrue(editor.是重大世界杯比赛(match, self.now))
        match["开球时间"] = "2026-07-17T08:00:00+08:00"
        self.assertFalse(editor.是重大世界杯比赛(match, self.now))

    def test_manual_pin_cannot_exceed_24_hours(self):
        item = self.article("pin", "普通行业动态", source="36氪", category="AI")
        pin = {"id": "pin", "editor": "test", "reason": "test", "starts_at": "2026-07-14T00:00:00+08:00", "expires_at": "2026-07-16T00:00:00+08:00"}
        _, headline, _ = self.select([item], {"pinned_headline": pin})
        self.assertIsNone(headline)

    def test_risky_article_requires_explicit_review(self):
        risky = self.article("risk", "新的诊断方法研究", 风险标签=["医疗"])
        _, _, rejected = self.select([risky])
        self.assertIn("unreviewed_content_risk:medical", [x["reason"] for x in rejected])
        risky["审核状态"] = "审核通过"
        chosen, _, _ = self.select([risky])
        self.assertEqual(chosen[0]["id"], "risk")
        english = self.article("privacy", "A report about personal data", risk_tags=["privacy"], reviewed="approved")
        chosen, _, _ = self.select([english])
        self.assertEqual(chosen[0]["id"], "privacy")

    def test_invalid_weight_override_is_ignored_and_audited(self):
        item = self.article("normal", "联合国发布全球安全报告")
        invalid = {"rule_version": "editorial-custom-v2", "weights": dict(editor.默认权重)}
        chosen, _, rejected = self.select([item], {"weight_overrides": invalid})
        self.assertEqual(chosen[0]["规则版本"], editor.规则版本)
        self.assertIn("weight_override_missing_review_metadata", [x["reason"] for x in rejected])

    def test_reviewed_weight_override_is_bounded_and_versioned(self):
        item = self.article("normal", "联合国发布全球安全报告")
        valid = {
            "rule_version": "editorial-reviewed-v2", "reviewed_by": "chief-editor",
            "reviewed_at": "2026-07-14T10:00:00+08:00", "weights": dict(editor.默认权重),
        }
        chosen, _, rejected = self.select([item], {"weight_overrides": valid})
        self.assertEqual(chosen[0]["规则版本"], "editorial-reviewed-v2")
        self.assertFalse(any(x.get("id") == "__weight_overrides__" for x in rejected))
        invalid = dict(valid, weights={**editor.默认权重, "真实图片": 50})
        _, _, rejected = self.select([item], {"weight_overrides": invalid})
        self.assertIn("weight_override_out_of_range", [x["reason"] for x in rejected])

    def test_short_titles_are_not_fuzzily_merged(self):
        first = self.article("s1", "停火谈判")
        second = self.article("s2", "停火协议")
        self.assertFalse(editor._近重复(first, second))


class PipelineGuardTests(unittest.TestCase):
    def test_official_museums_are_tier_a(self):
        for source in ("Rijksmuseum", "Art Institute of Chicago"):
            self.assertEqual(editor.来源等级({"来源": source}), ("A", 25))

    def test_pubmed_date_precision_and_missing_date(self):
        full = ET.fromstring("<x><PubDate><Year>2026</Year><Month>Jul</Month><Day>9</Day></PubDate></x>")
        year = ET.fromstring("<x><PubDate><Year>2025</Year></PubDate></x>")
        missing = ET.fromstring("<x />")
        self.assertEqual(collector._解析PubMed日期及精度(full), ("2026-07-09", "day"))
        self.assertEqual(collector._解析PubMed日期及精度(year), ("2025", "year"))
        self.assertEqual(collector._解析PubMed日期及精度(missing), ("", "unknown"))

    def test_pubmed_retraction_and_clinical_content_rejected(self):
        retracted = ET.fromstring("<x><PublicationType>Retracted Publication</PublicationType></x>")
        clinical = ET.fromstring("<x><PublicationType>Journal Article</PublicationType></x>")
        self.assertFalse(collector._PubMed情感研究合格(retracted, "Emotion regulation", "relationship study"))
        self.assertFalse(collector._PubMed情感研究合格(clinical, "Emotion regulation in PTSD patients", "treatment trial"))
        self.assertTrue(collector._PubMed情感研究合格(clinical, "Emotion regulation and friendship", "social connection among adults"))

    def test_new_batch_and_full_database_dedupe(self):
        base = {"id": 1, "标题": "AI 新闻", "摘要": "有效摘要", "日期": "2026-07-14"}
        batch = [base, dict(base, id=2), {"id": 3, "标题": "空摘要", "摘要": ""}]
        self.assertEqual(len(ai.文章去重(batch, [])), 1)
        self.assertEqual(len(ai.全库去重(batch)), 1)

    def test_english_ai_boundary(self):
        self.assertIsNotNone(editor.AI关键词.search("AI safety"))
        self.assertIsNone(editor.AI关键词.search("RAILWAY policy"))

    def test_change_registry_never_rebuilds_or_discards_history(self):
        original_path = ai.登记路径
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "修改登记.json"
            ai.登记路径 = path
            try:
                invalid = {"修改历史": []}
                path.write_text(json.dumps(invalid, ensure_ascii=False), encoding="utf-8")
                ai.登记修改(3)
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), invalid)

                valid = {
                    "铁律": "测试审计资产",
                    "修改历史": [{"id": 105, "改动摘要": "旧记录"}],
                    "files_last_modified": {"旧文件": {"最后修改者": "test"}},
                    "最后更新": "2026-07-14T00:00:00+08:00",
                }
                path.write_text(json.dumps(valid, ensure_ascii=False), encoding="utf-8")
                ai.登记修改(3)
                updated = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(updated["修改历史"][0]["id"], 106)
                self.assertEqual(updated["修改历史"][1], valid["修改历史"][0])
                self.assertIn("旧文件", updated["files_last_modified"])
            finally:
                ai.登记路径 = original_path


if __name__ == "__main__":
    unittest.main()
