import json
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))
from voc import baselines, extract, gate, metrics  # noqa: E402
from voc.llm import LLM, ProviderError, estimate_cost  # noqa: E402
from voc.validate import check_label  # noqa: E402

TEXT = "withdrawal stuck for two days, support is not helping"


def good_label(rid="r1"):
    return {"reviewId": rid, "usable": True, "overall_sentiment": "negative", "aspects": [
        {"category": "payments_funds", "aspect": "withdrawal stuck", "sentiment": "negative",
         "severity": "high", "quote": "withdrawal stuck for two days"}]}


class StubClient:
    """Mimics client.messages.create. `script` is a list of callables or response dicts."""
    def __init__(self, script):
        self.script, self.calls = list(script), 0
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls += 1
        item = self.script.pop(0)
        if item == "refuse":
            return SimpleNamespace(stop_reason="refusal", stop_details=SimpleNamespace(category="general_harms"),
                                   content=[], usage=SimpleNamespace(input_tokens=10, output_tokens=0), _request_id="x")
        return SimpleNamespace(stop_reason="end_turn", stop_details=None,
                               content=[SimpleNamespace(type="text", text=json.dumps(item))],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=100,
                                                     cache_creation_input_tokens=0, cache_read_input_tokens=0),
                               _request_id="x")


class ValidateTests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(check_label(good_label(), TEXT), [])

    def test_bad_quote_and_category(self):
        l = good_label()
        l["aspects"][0]["quote"] = "not in review"
        l["aspects"][0]["category"] = "bugs"
        errs = check_label(l, TEXT)
        self.assertEqual(len(errs), 2)

    def test_too_many_aspects(self):
        l = good_label()
        l["aspects"] = l["aspects"] * 4
        self.assertTrue(any("max is" in e for e in check_label(l, TEXT)))


class GateTests(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(gate.gate("good app", 5)[0], "skip")
        self.assertEqual(gate.gate("withdraw stuck", 5)[0], "pass")
        self.assertEqual(gate.gate("bahut bekar app hai", 5)[0], "pass")
        self.assertEqual(gate.gate("app is worst", 1)[0], "pass")
        self.assertEqual(gate.gate("great", 5)[0], "skip")


class MetricTests(unittest.TestCase):
    def test_kappa_perfect_and_matching(self):
        self.assertAlmostEqual(metrics.cohen_kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"], ["a", "b"]), 1.0)
        g = [{"category": "crash_bug", "quote": "screen locks up while trading"}]
        p = [{"category": "crash_bug", "quote": "locks up while trading"}]
        self.assertEqual(metrics.match_aspects(g, p), [(0, 0)])
        p[0]["category"] = "performance"
        self.assertEqual(metrics.match_aspects(g, p), [])

    def test_short_quote_inside_long_quote_matches_under_overlap_only(self):
        g = [{"category": "payments_funds", "quote": "refund delayed, my money is stuck, support unreachable, no update"}]
        p = [{"category": "payments_funds", "quote": "my money is stuck"}]
        self.assertEqual(metrics.match_aspects(g, p), [(0, 0)])
        self.assertEqual(metrics.match_aspects(g, p, mode="jaccard"), [])

    def test_evaluate_perfect(self):
        gold = {"r1": good_label()}
        m = metrics.evaluate(gold, gold, ["r1"])
        self.assertEqual(m["aspect"]["f1"], 1.0)
        self.assertEqual(m["usable"]["recall"], 1.0)

    def test_missing_prediction_counts_as_miss(self):
        m = metrics.evaluate({"r1": good_label()}, {}, ["r1"])
        self.assertEqual(m["missing_predictions"], 1)
        self.assertEqual(m["aspect"]["fn"], 1)


class BaselineTests(unittest.TestCase):
    def test_baselines_emit_valid_labels(self):
        for text, score in [(TEXT, 1), ("good app", 5), ("please add dark mode, ui is confusing", 3), ("ok", 4)]:
            r = {"reviewId": "r", "content": text, "score": score}
            for fn in baselines.KINDS.values():
                self.assertEqual(check_label(fn(r), text), [], (fn.__name__, text))


class ExtractTests(unittest.TestCase):
    review = {"reviewId": "r1", "content": TEXT, "score": 1}

    def run_case(self, script):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        client = StubClient(script)
        llm = LLM(d + "/c.db", client=client)
        res = extract.extract_review(llm, self.review, "sys", ["claude-small", "claude-big"], "low")
        return res, client, llm

    def test_ok_first_try_and_cache(self):
        res, client, llm = self.run_case([good_label()])
        self.assertEqual((res["status"], res["model"], client.calls), ("ok", "claude-small", 1))
        res2 = extract.extract_review(llm, self.review, "sys", ["claude-small", "claude-big"], "low")
        self.assertEqual(client.calls, 1)  # served from cache
        self.assertEqual(res2["usage"]["cached_calls"], 1)

    def test_invalid_then_retry_ok(self):
        bad = good_label()
        bad["aspects"][0]["quote"] = "made up"
        res, client, _ = self.run_case([bad, good_label()])
        self.assertEqual((res["status"], client.calls), ("ok", 2))

    def test_escalates_after_two_failures(self):
        bad = good_label()
        bad["aspects"][0]["quote"] = "made up"
        res, client, _ = self.run_case([bad, bad, good_label()])
        self.assertEqual((res["status"], res["model"], client.calls), ("ok", "claude-big", 3))

    def test_refusal_then_escalate(self):
        res, client, _ = self.run_case(["refuse", good_label()])
        self.assertEqual((res["status"], res["model"]), ("ok", "claude-big"))

    def test_all_refused(self):
        res, _, _ = self.run_case(["refuse", "refuse"])
        self.assertEqual(res["status"], "refused")

    def test_cost_estimate(self):
        c = estimate_cost("claude-haiku-5-5", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
        self.assertAlmostEqual(c, 0.60)


def lab_for(rid, text):
    q = " ".join(text.split()[:3])
    return {"reviewId": rid, "usable": True, "overall_sentiment": "negative", "aspects": [
        {"category": "crash_bug", "aspect": "app problem", "sentiment": "negative",
         "severity": "high", "quote": q}]}


def groq_ok(payload, finish="stop"):
    return (200, {}, {"id": "g1", "choices": [{"message": {"content": json.dumps(payload)},
                                                 "finish_reason": finish}],
                      "usage": {"prompt_tokens": 2000, "completion_tokens": 150}})


class GroqTests(unittest.TestCase):
    def make(self, responses):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        bodies, sleeps = [], []

        def post(url, headers, body):
            bodies.append(body)
            return responses.pop(0)

        return LLM(d + "/c.db", groq_post=post, sleep=sleeps.append), bodies, sleeps

    def call(self, llm, model="openai/gpt-oss-120b"):
        return llm.call(model=model, system="s", user="u", schema={"type": "object"}, effort="low")

    def test_strict_schema_for_gpt_oss_and_usage_mapping(self):
        llm, bodies, _ = self.make([groq_ok({"a": 1})])
        res = self.call(llm)
        fmt = bodies[0]["response_format"]
        self.assertEqual((fmt["type"], fmt["json_schema"]["strict"]), ("json_schema", True))
        self.assertEqual((res.usage["input_tokens"], res.usage["output_tokens"], res.cost_usd), (2000, 150, 0.0))

    def test_json_mode_for_other_models(self):
        llm, bodies, _ = self.make([groq_ok({"a": 1})])
        self.call(llm, "llama-3.3-70b-versatile")
        self.assertEqual(bodies[0]["response_format"], {"type": "json_object"})
        self.assertIn("schema", bodies[0]["messages"][0]["content"])

    def test_rate_limit_waits_then_succeeds(self):
        llm, bodies, sleeps = self.make([(429, {"Retry-After": "7"}, {}), groq_ok({"a": 1})])
        self.call(llm)
        self.assertEqual((len(bodies), sleeps), (2, [7.0]))

    def test_network_error_is_retried(self):
        import urllib.error
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        seq = [urllib.error.URLError("handshake timed out"), groq_ok({"a": 1})]
        sleeps = []

        def post(u, h, b):
            x = seq.pop(0)
            if isinstance(x, Exception):
                raise x
            return x

        llm = LLM(d + "/c.db", groq_post=post, sleep=sleeps.append)
        res = self.call(llm)
        self.assertEqual((res.text, sleeps), ('{"a": 1}', [5.0]))

    def test_client_error_raises_without_secrets(self):
        llm, _, _ = self.make([(400, {}, {"error": {"message": "bad schema"}})])
        with self.assertRaises(ProviderError) as cm:
            self.call(llm)
        self.assertIn("bad schema", str(cm.exception))

    def test_truncated_answer_not_cached(self):
        llm, bodies, _ = self.make([groq_ok({"a": 1}, finish="length"), groq_ok({"a": 1})])
        self.call(llm)
        self.call(llm)
        self.assertEqual(len(bodies), 2)


class GroqRobustnessTests(GroqTests):
    def test_reasoning_effort_sent_for_gpt_oss_only(self):
        llm, bodies, _ = self.make([groq_ok({"a": 1}), groq_ok({"a": 1})])
        self.call(llm)
        self.call(llm, "llama-3.3-70b-versatile")
        self.assertEqual(bodies[0]["reasoning_effort"], "low")
        self.assertNotIn("reasoning_effort", bodies[1])

    def test_invalid_json_error_becomes_failure_not_crash(self):
        bad = (400, {}, {"error": {"message": "x", "code": "json_validate_failed"}})
        review = {"reviewId": "r1", "content": "withdrawal stuck for two days", "score": 1}
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        responses = [bad, groq_ok(lab_for("r1", review["content"]))]
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: responses.pop(0), sleep=lambda s: None)
        res = extract.extract_review(llm, review, "sys", ["openai/gpt-oss-120b"], "low")
        self.assertEqual(res["status"], "ok")  # first attempt failed, retry succeeded


class BatchTests(unittest.TestCase):
    reviews = [{"reviewId": "r%d" % i, "content": "app problem number %d here" % i, "score": 1} for i in range(3)]

    def run_batch(self, responses):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        bodies = []

        def post(url, headers, body):
            bodies.append(body)
            return responses.pop(0)

        llm = LLM(d + "/c.db", groq_post=post, sleep=lambda s: None)
        meta = extract.run_extraction(self.reviews, llm, "sys", ["openai/gpt-oss-120b"], "low", 1,
                                      d + "/out", batch_size=3, system_batch="sysb")
        lines = open(d + "/out/labels.jsonl").read().strip().splitlines()
        return meta, bodies, lines

    def test_all_valid_in_one_call(self):
        labels = [lab_for(r["reviewId"], r["content"]) for r in self.reviews]
        meta, bodies, lines = self.run_batch([groq_ok({"labels": labels})])
        self.assertEqual((len(bodies), meta["status"], len(lines)), (1, {"ok": 3}, 3))

    def test_missing_label_falls_back_to_single_call(self):
        labels = [lab_for(r["reviewId"], r["content"]) for r in self.reviews]
        responses = [groq_ok({"labels": labels[:2]}), groq_ok(labels[2])]
        meta, bodies, lines = self.run_batch(responses)
        self.assertEqual((len(bodies), meta["status"], meta["single_path_retries"], len(lines)),
                         (2, {"ok": 3}, 1, 3))

    def test_one_review_label_cannot_pass_with_wrong_quote(self):
        labels = [lab_for(r["reviewId"], r["content"]) for r in self.reviews]
        labels[1]["aspects"][0]["quote"] = "not in the review"
        responses = [groq_ok({"labels": labels}), groq_ok(lab_for("r1", self.reviews[1]["content"]))]
        meta, bodies, _ = self.run_batch(responses)
        self.assertEqual((meta["status"], meta["single_path_retries"]), ({"ok": 3}, 1))


def flags(**on):
    base = {"event_described": False, "money_lost": False, "money_blocked": False, "loss_amount_stated": False,
            "order_wrong": False, "core_action_blocked": False, "workaround_mentioned": False,
            "security_or_data_issue": False}
    base.update(on)
    return base


def asp(category="crash_bug", sentiment="negative", **on):
    return {"category": category, "aspect": "x", "sentiment": sentiment, "quote": "q", "impact": flags(**on)}


class SeverityRuleTests(unittest.TestCase):
    def sev(self, *a, **k):
        from voc.severity import derive_severity
        return derive_severity(asp(*a, **k))

    def test_rules_follow_the_approved_policy(self):
        self.assertEqual(self.sev("fraud_money_loss_claim"), "low")                          # generic accusation
        self.assertEqual(self.sev("customer_support"), "low")                                # generic support abuse
        self.assertEqual(self.sev("crash_bug", event_described=True), "medium")              # vague not working
        self.assertEqual(self.sev("payments_funds", event_described=True, money_blocked=True), "critical")
        self.assertEqual(self.sev("fraud_money_loss_claim", money_lost=True), "critical")
        self.assertEqual(self.sev("order_execution", order_wrong=True), "critical")
        self.assertEqual(self.sev("login_kyc_account", core_action_blocked=True), "high")
        self.assertEqual(self.sev("login_kyc_account", core_action_blocked=True, workaround_mentioned=True), "medium")
        self.assertEqual(self.sev("charges_pricing", loss_amount_stated=True), "critical")
        self.assertEqual(self.sev("feature_request", event_described=True), "low")
        self.assertEqual(self.sev("login_kyc_account", security_or_data_issue=True), "critical")

    def test_none_for_positive_praise_other(self):
        self.assertEqual(self.sev("praise", "positive"), "none")
        self.assertEqual(self.sev("other", "negative", money_lost=True), "none")
        self.assertEqual(self.sev("crash_bug", "neutral", event_described=True), "none")

    def test_finalize_adds_severity_and_rejects_bad_flags(self):
        from voc.severity import finalize_label
        label = {"reviewId": "r", "usable": True, "overall_sentiment": "negative",
                 "aspects": [asp("payments_funds", money_blocked=True)]}
        out = finalize_label(label)
        self.assertEqual(out["aspects"][0]["severity"], "critical")
        self.assertNotIn("severity", label["aspects"][0])  # input untouched
        label["aspects"][0]["impact"]["money_lost"] = "yes"
        with self.assertRaises(ValueError):
            finalize_label(label)


class GroqLimitTests(unittest.TestCase):
    def test_request_larger_than_minute_limit_raises_without_retry(self):
        msg = "Rate limit reached ... tokens per minute (TPM): Limit 8000, Used 0, Requested 9100. Please try again"
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        calls = []

        def post(u, h, b):
            calls.append(1)
            return (429, {}, {"error": {"message": msg, "code": "rate_limit_exceeded"}})

        llm = LLM(d + "/c.db", groq_post=post, sleep=lambda s: None)
        with self.assertRaises(ProviderError) as cm:
            llm.call(model="openai/gpt-oss-120b", system="s", user="u", schema={"type": "object"}, effort="low")
        self.assertEqual((cm.exception.code, len(calls)), ("request_too_large", 1))

    def test_daily_limit_waits_long_then_reports_clearly(self):
        msg = "Rate limit reached ... on tokens per day (TPD): Limit 200000, Used 197358, Requested 4051."
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        sleeps = []
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: (429, {"retry-after": "609"}, {"error": {"message": msg}}),
                  sleep=sleeps.append)
        with self.assertRaises(ProviderError) as cm:
            llm.call(model="openai/gpt-oss-120b", system="s", user="u", schema={"type": "object"}, effort="low")
        self.assertEqual(cm.exception.code, "daily_limit")
        self.assertEqual(sleeps[0], 609.0)  # waited the full retry-after, not the 90 s cap

    def test_budget_shrinks_to_fit_minute_limit(self):
        small = extract.budget("openai/gpt-oss-120b", "x" * 1000, "y" * 1000, 6, "flags")
        big = extract.budget("openai/gpt-oss-120b", "x" * 13000, "y" * 3000, 6, "flags")
        self.assertGreater(small, big)
        self.assertLessEqual(big, 7600 - int(16000 / 3.2))

    def test_oversized_batch_falls_back_to_single_calls(self):
        reviews = [{"reviewId": "r%d" % i, "content": "app problem number %d here" % i, "score": 1} for i in range(2)]
        too_big = (429, {}, {"error": {"message": "Limit 8000, Used 0, Requested 9100", "code": "x"}})
        responses = [too_big, groq_ok(lab_for("r0", reviews[0]["content"])),
                     groq_ok(lab_for("r1", reviews[1]["content"]))]
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: responses.pop(0), sleep=lambda s: None)
        meta = extract.run_extraction(reviews, llm, "sys", ["openai/gpt-oss-120b"], "low", 1, d + "/out",
                                      batch_size=2, system_batch="sysb")
        self.assertEqual((meta["status"], meta["single_path_retries"]), ({"ok": 2}, 2))


class FlagsModeExtractionTests(unittest.TestCase):
    def test_flags_label_is_finalized_and_validated(self):
        text = "my withdrawal is stuck for two days"
        review = {"reviewId": "r1", "content": text, "score": 1}
        a = asp("payments_funds", money_blocked=True, event_described=True)
        a.update({"aspect": "withdrawal stuck", "quote": "my withdrawal is stuck"})
        raw = {"reviewId": "r1", "usable": True, "overall_sentiment": "negative", "aspects": [a]}
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: groq_ok(raw), sleep=lambda s: None)
        res = extract.extract_review(llm, review, "sys", ["openai/gpt-oss-120b"], "low", mode="flags")
        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["label"]["aspects"][0]["severity"], "critical")
        self.assertEqual(check_label(res["label"], text), [])

    def test_missing_flags_fail_validation_path(self):
        review = {"reviewId": "r1", "content": "withdrawal stuck now", "score": 1}
        bad = {"reviewId": "r1", "usable": True, "overall_sentiment": "negative", "aspects": [
            {"category": "payments_funds", "aspect": "stuck", "sentiment": "negative", "quote": "withdrawal stuck"}]}
        label, errs = extract._check(bad, review, "flags")
        self.assertIsNone(label)
        self.assertTrue(errs[0].startswith("bad impact flags"))


class ThemeTests(unittest.TestCase):
    def test_similar_phrases_group_within_category_only(self):
        from voc import themes
        asp = [{"review_id": "r%d" % i, "category": c, "aspect": a} for i, (c, a) in enumerate([
            ("payments_funds", "withdrawal delay"), ("payments_funds", "withdrawal delayed"),
            ("payments_funds", "withdrawal delay again"), ("payments_funds", "upi payment failed"),
            ("login_kyc_account", "withdrawal delay")])]
        t = themes.build_themes(asp, threshold=0.3, min_size=3)
        ids = [a["theme_id"] for a in asp]
        self.assertEqual(ids[0], ids[1])
        self.assertEqual(ids[0], ids[2])
        self.assertNotEqual(ids[0], ids[3])
        self.assertNotEqual(ids[0], ids[4])  # same words, different category: never merged
        big = [x for x in t if x["theme_id"] == ids[0]][0]
        self.assertEqual((big["review_count"], big["status"]), (3, "ranked"))


class AggregateTests(unittest.TestCase):
    def test_priority_and_rating_drag(self):
        from voc import aggregate
        reviews = [{"review_id": "a", "date": "2026-10-10", "score": 1}, {"review_id": "b", "date": "2026-10-11", "score": 1},
                   {"review_id": "c", "date": "2026-10-12", "score": 5}, {"review_id": "d", "date": "2026-10-13", "score": 5}]
        aspects = [{"review_id": "a", "severity": "critical", "theme_id": "t1"},
                   {"review_id": "b", "severity": "high", "theme_id": "t1"}]
        out = aggregate.rank_themes(reviews, aspects, [{"theme_id": "t1", "name": "x", "category": "c"}],
                                    "2026-10-01", "2026-10-31")
        t = out[0]
        self.assertEqual((t["reviews"], t["severity_score"], t["trend"], t["priority"]), (2, 12, 1.0, 12.0))
        self.assertAlmostEqual(t["rating_drag"], (4 + 4) / 4)  # others average 5; two reviews 4 below, over 4 reviews
        self.assertEqual(t["status"], "emerging")

    def test_trend_uses_previous_window_and_is_clamped(self):
        from voc import aggregate
        reviews = [{"review_id": "p1", "date": "2026-09-10", "score": 1}] + \
                  [{"review_id": "n%d" % i, "date": "2026-10-10", "score": 1} for i in range(9)]
        aspects = [{"review_id": r["review_id"], "severity": "low", "theme_id": "t"} for r in reviews]
        out = aggregate.rank_themes(reviews, aspects, [], "2026-10-01", "2026-10-31", "2026-09-01", "2026-09-30")
        self.assertAlmostEqual(out[0]["trend"], 10 / 2)
        self.assertAlmostEqual(out[0]["priority"], 9 * 1 * 2.0)  # multiplier clamped at 2


class RegressionTests(unittest.TestCase):
    def test_fisher_and_bh_known_values(self):
        from voc import regress
        self.assertAlmostEqual(regress.fisher_exact(8, 2, 1, 5), 0.0350, places=3)
        self.assertEqual([round(x, 3) for x in regress.bh_adjust([0.01, 0.04, 0.03])], [0.03, 0.04, 0.04])

    def test_flags_only_with_enough_data_and_a_real_rise(self):
        from voc import regress
        rev = [{"review_id": "a%d" % i, "version": "18.1.0", "score": 1 if i < 4 else 5} for i in range(40)] + \
              [{"review_id": "b%d" % i, "version": "18.2.0", "score": 1 if i < 20 else 5} for i in range(40)] + \
              [{"review_id": "c%d" % i, "version": "18.3.0", "score": 1} for i in range(5)]
        res = regress.compare(rev, [])
        first = [r for r in res if r["version"] == "18.2.0" and r["subject"] == "negative_share"][0]
        self.assertTrue(first["flag"])
        small = [r for r in res if r["version"] == "18.3.0"][0]
        self.assertFalse(small["flag"])
        self.assertIn("insufficient", small["why"])

    def test_unknown_version_is_its_own_bucket(self):
        from voc import regress
        rev = [{"review_id": "x", "version": "unknown", "score": 1}, {"review_id": "y", "version": "18.1.0", "score": 5}]
        self.assertEqual(regress.unknown_bucket(rev), {"n": 1, "negative_share": 1.0})
        self.assertEqual(regress.compare(rev, []), [])  # one known version: nothing to compare


class AppDataTests(unittest.TestCase):
    def snap(self):
        reviews = [{"review_id": "r%d" % i, "date": "2026-10-%02d" % (10 + i % 10), "score": 1 if i < 6 else 5,
                    "version": "18.1.0" if i < 5 else "unknown", "text": "text %d" % i} for i in range(12)]
        aspects = [{"review_id": "r%d" % i, "category": "payments_funds", "aspect": "withdrawal delay", "sentiment": "negative",
                    "severity": "critical" if i < 3 else "low", "quote": "q", "impact": {"money_blocked": True} if i < 3 else {},
                    "theme_id": "payments_funds:1"} for i in range(6)]
        themes = [{"theme_id": "payments_funds:1", "category": "payments_funds", "name": "Withdrawal delays", "size": 6,
                   "review_count": 6, "status": "ranked", "samples": ["withdrawal delay"]}]
        return {"meta": {"date_from": "2026-10-10", "date_to": "2026-10-19"}, "reviews": reviews, "aspects": aspects,
                "themes": themes}

    def test_previous_window_and_neutral_trend_before_data_start(self):
        from voc import appdata
        self.assertEqual(appdata.previous_window("2026-10-11", "2026-10-20"), ("2026-10-01", "2026-10-10"))
        rows, trend_ok = appdata.ranking(self.snap(), "2026-10-10", "2026-10-19")
        self.assertFalse(trend_ok)               # previous window starts before the data: trend neutral
        self.assertEqual(rows[0]["trend"], 1.0)

    def test_weights_change_priority_and_min_size_changes_status(self):
        from voc import appdata
        s = self.snap()
        base, _ = appdata.ranking(s, "2026-10-10", "2026-10-19")
        heavy, _ = appdata.ranking(s, "2026-10-10", "2026-10-19", {"critical": 20, "high": 4, "medium": 2, "low": 1, "none": 0})
        self.assertGreater(heavy[0]["priority"], base[0]["priority"])
        strict, _ = appdata.ranking(s, "2026-10-10", "2026-10-19", None, 10)
        self.assertEqual(strict[0]["status"], "emerging")

    def test_theme_detail_orders_most_severe_first_and_counts(self):
        from voc import appdata
        d = appdata.theme_detail(self.snap(), "payments_funds:1", "2026-10-10", "2026-10-19")
        self.assertEqual(len(d["reviews"]), 6)
        self.assertEqual(d["reviews"][0]["severity"], "critical")
        self.assertEqual(d["severity_mix"], {"critical": 3, "low": 3})
        self.assertEqual(d["reviews"][0]["aspects"][0]["flags"], ["money_blocked"])

    def test_live_feature_cache_does_not_need_a_data_folder(self):
        import os
        from voc import appdata
        path = appdata.live_cache_path()
        self.assertTrue(os.path.isdir(os.path.dirname(path)))     # the folder exists on any machine
        LLM(path)                                                  # and the cache can be created there
        self.assertNotIn("data" + os.sep, path.replace(os.path.dirname(path), ""))

    def test_plain_facts_hides_event_described_and_uses_plain_words(self):
        from voc import appdata
        impact = {"event_described": True, "money_blocked": True, "core_action_blocked": True, "order_wrong": False}
        self.assertEqual(appdata.plain_facts(impact), ["money stuck or delayed", "couldn't complete a main action"])
        self.assertEqual(appdata.plain_facts({"event_described": True}), [])
        self.assertEqual(appdata.plain_facts(None), [])

    def test_release_table_keeps_unknown_separate(self):
        from voc import appdata
        rt = appdata.release_table(self.snap())
        self.assertEqual([v["version"] for v in rt["versions"]], ["18.1.0"])
        self.assertEqual(rt["unknown"]["n"], 7)
        self.assertEqual(rt["comparisons"], [])  # one known version: nothing to compare


class LatencyLogTests(unittest.TestCase):
    def test_real_calls_are_logged_and_cached_calls_are_not(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: groq_ok({"a": 1}), sleep=lambda s: None)
        for _ in range(2):  # second call is served from the cache
            llm.call(model="openai/gpt-oss-20b", system="s", user="u", schema={"type": "object"}, effort="low")
        lines = [json.loads(l) for l in open(d + "/c.db.calls.jsonl")]
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0]["model"], lines[0]["input_tokens"], lines[0]["output_tokens"]),
                         ("openai/gpt-oss-20b", 2000, 150))
        self.assertIn("latency_s", lines[0])


class DemoSnapshotTests(unittest.TestCase):
    path = pathlib.Path(__file__).resolve().parent.parent / "app" / "demo_snapshot.json"

    def snap(self):
        return json.load(open(self.path))

    def test_demo_is_labeled_invented_and_names_no_real_company(self):
        s = self.snap()
        self.assertTrue(s["meta"]["demo"])
        self.assertIn("fictional", s["meta"]["app"])
        blob = self.path.read_text().lower()
        for real_name in ("groww", "zerodha", "upstox", "angel one"):
            self.assertNotIn(real_name, blob)

    def test_demo_labels_follow_the_real_pipeline_rules(self):
        from voc.severity import derive_severity
        s = self.snap()
        text = {r["review_id"]: r["text"] for r in s["reviews"]}
        for a in s["aspects"]:
            self.assertIn(a["quote"], text[a["review_id"]])            # quotes are word for word
            if a["category"] != "praise":
                self.assertEqual(a["severity"], derive_severity(a))     # severity comes from the facts by the same rules

    def test_the_whole_app_logic_runs_on_the_demo(self):
        from voc import appdata
        s = self.snap()
        rows, _ = appdata.ranking(s, s["meta"]["date_from"], s["meta"]["date_to"])
        self.assertGreaterEqual(len([r for r in rows if r["status"] == "ranked"]), 8)
        brief = appdata.build_brief(s, "2026-10-17", "2026-10-30", None, 5)
        self.assertEqual(appdata.check_brief(s, brief), [])
        self.assertGreaterEqual(len(brief["fix_first"]), 2)
        self.assertTrue(appdata.release_table(s)["versions"])
        md = appdata.render_markdown(brief)
        self.assertNotIn("groww", md.lower())                               # the brief never names a real company in the demo
        self.assertIn("Demo Invest", md)
        ids = [q["review_id"] for t in brief["fix_first"] for q in t["quotes"]]
        self.assertTrue(all(appdata._short_id(i) == i for i in ids))        # demo ids are shown in full, so no two look the same

    def test_no_real_review_text_is_in_the_demo(self):
        from voc import publiccheck
        real = publiccheck.real_shingles(str(pathlib.Path(__file__).resolve().parent.parent / "data" / "raw"))
        if not real:
            self.skipTest("real reviews are not on this machine")
        joined = " \n ".join(r["text"] for r in self.snap()["reviews"])
        self.assertEqual(publiccheck.overlaps(joined, real), [])


class RejectionLogTests(unittest.TestCase):
    reviews = [{"reviewId": "r%d" % i, "content": "app problem number %d here" % i, "score": 1} for i in range(3)]

    def run_case(self, responses):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: responses.pop(0), sleep=lambda s: None)
        meta = extract.run_extraction(self.reviews, llm, "sys", ["openai/gpt-oss-120b"], "low", 1, d + "/out",
                                      batch_size=3, system_batch="sysb")
        return meta, d

    def test_reasons_are_classified_and_counted(self):
        from voc import rejections
        self.assertEqual(rejections.classify_reason("quote not found verbatim in review: 'x'"), "quote_not_verbatim")
        self.assertEqual(rejections.classify_reason("bad category 'bugs'"), "invalid_category")
        self.assertEqual(rejections.classify_reason("3 aspects, max is 3"), "too_many_aspects")
        self.assertEqual(rejections.classify_reason("bad impact flags: missing"), "missing_or_invalid_flags")
        self.assertEqual(rejections.classify_reason("something new"), "other")

    def test_invented_quote_and_missing_label_are_logged_and_the_rate_is_correct(self):
        good = [lab_for(r["reviewId"], r["content"]) for r in self.reviews]
        bad_quote = lab_for("r1", self.reviews[1]["content"])
        bad_quote["aspects"][0]["quote"] = "words nobody wrote"
        responses = [groq_ok({"labels": [good[0], bad_quote]}),   # r1 invented a quote, r2 was skipped
                     groq_ok(good[1]), groq_ok(good[2])]           # both redone one at a time
        meta, d = self.run_case(responses)
        self.assertEqual(meta["status"], {"ok": 3})
        r = meta["rejections"]
        self.assertEqual((r["answers_checked"], r["answers_rejected"]), (5, 2))
        self.assertEqual(r["by_reason"], {"quote_not_verbatim": 1, "label_missing_from_batch": 1})
        self.assertEqual((r["quotes_checked"], r["quotes_not_verbatim"]), (4, 1))
        self.assertEqual((r["quotes_invented"], r["quotes_altered"], r["invented_quote_rate"]), (1, 0, 0.25))
        lines = [json.loads(l) for l in open(d + "/out/rejections.jsonl")]
        self.assertEqual(sorted(e["kind"] for e in lines), ["check", "check", "check", "check", "missing"])

    def test_a_small_change_is_called_altered_and_a_different_sentence_invented(self):
        from voc import rejections
        text = "Please add a portfolio summary page, with a simple weekly profit chart"
        self.assertEqual(rejections.quote_kind(rejections.quote_similarity("Please add a portfolio summary page with a simple weekly profit chart", text)), "altered")
        self.assertEqual(rejections.quote_kind(rejections.quote_similarity("everything works perfectly and support replied at once", text)), "invented")

    def test_whole_batch_failure_counts_every_review(self):
        too_long = (400, {}, {"error": {"message": "x", "code": "json_validate_failed"}})
        good = [lab_for(r["reviewId"], r["content"]) for r in self.reviews]
        meta, _ = self.run_case([too_long] + [groq_ok(g) for g in good])
        r = meta["rejections"]
        self.assertEqual((r["answers_checked"], r["answers_rejected"]), (6, 3))
        self.assertEqual(r["by_reason"], {"provider_token_cap": 3})


class WeeklyBriefTests(unittest.TestCase):
    def snap(self):
        reviews = [{"review_id": "r%02d" % i, "date": "2026-10-%02d" % (1 + i), "score": 1 if i % 2 == 0 else 5,
                    "version": "unknown", "text": "review text number %d about the problem" % i} for i in range(24)]

        def asp(i, theme, cat, sev):
            return {"review_id": "r%02d" % i, "category": cat, "aspect": "x", "sentiment": "negative", "severity": sev,
                    "quote": "q", "impact": {}, "theme_id": theme}
        aspects = [asp(i, "payments_funds:1", "payments_funds", "critical" if i < 17 else "low") for i in list(range(14, 24)) + [4, 5]]
        aspects += [asp(i, "fraud_money_loss_claim:1", "fraud_money_loss_claim", "medium") for i in range(18, 24)]
        themes = [{"theme_id": "payments_funds:1", "category": "payments_funds", "name": "Withdrawal delays", "size": 12,
                   "review_count": 12, "status": "ranked", "samples": ["x"]},
                  {"theme_id": "fraud_money_loss_claim:1", "category": "fraud_money_loss_claim", "name": "Claims of money loss",
                   "size": 6, "review_count": 6, "status": "ranked", "samples": ["x"]}]
        return {"meta": {"date_from": "2026-10-01", "date_to": "2026-10-24", "n_reviews": 24}, "reviews": reviews,
                "aspects": aspects, "themes": themes}

    def test_brief_separates_claims_flags_rising_and_passes_its_own_checks(self):
        from voc import appdata
        s = self.snap()
        b = appdata.build_brief(s, "2026-10-15", "2026-10-24", None, 5)
        self.assertEqual([t["name"] for t in b["fix_first"]], ["Withdrawal delays"])        # claims never enter the fix list
        self.assertEqual([t["name"] for t in b["risk"]], ["Claims of money loss"])
        self.assertEqual(b["requests"], [])
        self.assertEqual([t["name"] for t in b["rising"]], ["Withdrawal delays"])           # 10 now versus 2 before
        self.assertEqual(appdata.check_brief(s, b), [])
        md = appdata.render_markdown(b)
        self.assertIn("Withdrawal delays", md)
        self.assertIn("not verified facts", md)
        self.assertIn("Up from 2 last period", md)
        self.assertIn("Small sample", md)                                                  # under 30 reviews is flagged

    def test_check_catches_an_invented_quote_a_missing_review_and_a_thin_theme(self):
        from voc import appdata
        s = self.snap()
        b = appdata.build_brief(s, "2026-10-15", "2026-10-24", None, 5)
        b["fix_first"][0]["quotes"][0]["excerpt"] = "something nobody wrote"
        b["fix_first"][0]["quotes"][1]["review_id"] = "does-not-exist"
        b["fix_first"][0]["reviews"] = 2
        problems = appdata.check_brief(s, b)
        self.assertEqual(len(problems), 3)

    def test_no_trend_when_the_previous_period_starts_before_the_data(self):
        from voc import appdata
        b = appdata.build_brief(self.snap(), "2026-10-01", "2026-10-24", None, 5)
        self.assertIsNone(b["prev_headline"])
        self.assertEqual(b["rising"], [])
        self.assertIn("no earlier period", appdata.render_markdown(b))

    def test_excerpt_keeps_the_start_of_the_text_word_for_word(self):
        from voc import appdata
        long = "word " * 100
        ex = appdata.excerpt(long, 50)
        self.assertTrue(ex.endswith(" …"))
        self.assertTrue(" ".join(long.split()).startswith(ex.removesuffix(" …")))


class DailyLimitStopTests(unittest.TestCase):
    daily = (429, {"retry-after": "600"}, {"error": {"message": "tokens per day (TPD): Limit 200000, Used 199000, Requested 4000"}})

    def test_llm_fails_fast_without_sleeping_when_told_not_to_wait(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        sleeps = []
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: self.daily, sleep=sleeps.append, wait_on_daily=False)
        with self.assertRaises(ProviderError) as cm:
            llm.call(model="openai/gpt-oss-20b", system="s", user="u", schema={"type": "object"}, effort="low")
        self.assertEqual((cm.exception.code, sleeps), ("daily_limit", []))

    def test_run_stops_cleanly_keeps_finished_reviews_and_marks_rest_not_run(self):
        reviews = [{"reviewId": "r%d" % i, "content": "app problem number %d here" % i, "score": 1} for i in range(4)]
        first = groq_ok({"labels": [lab_for(r["reviewId"], r["content"]) for r in reviews[:2]]})
        responses = [first]

        def post(u, h, b):
            return responses.pop(0) if responses else self.daily

        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        llm = LLM(d + "/c.db", groq_post=post, sleep=lambda s: None, wait_on_daily=False)
        meta = extract.run_extraction(reviews, llm, "sys", ["openai/gpt-oss-20b"], "low", 1, d + "/out",
                                      batch_size=2, system_batch="sysb")
        self.assertEqual((meta["status"], meta["stopped_on_daily_limit"]), ({"ok": 2, "not_run": 2}, True))
        with open(d + "/out/labels.jsonl") as f:
            self.assertEqual(len(f.read().strip().splitlines()), 2)


class ThemeMergeTests(unittest.TestCase):
    def test_validate_drops_invented_ids_and_keeps_forgotten_clusters(self):
        from voc import theme_merge
        groups = [{"name": "A", "cluster_ids": ["c1", "c2", "c9"]},   # c9 was never offered
                  {"name": "B", "cluster_ids": ["c2"]}]                # c2 already used
        out, dropped, added = theme_merge.validate_groups(groups, 4)
        self.assertEqual((dropped, added), (2, 2))                     # c9 and the second c2; c3, c4 forgotten
        self.assertEqual(sorted(i for g in out for i in g["members"]), [0, 1, 2, 3])  # every cluster exactly once

    def test_merge_all_combines_within_category_and_updates_aspects(self):
        from voc import theme_merge
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        aspects = [{"review_id": "r%d" % i, "category": "payments_funds", "theme_id": "payments_funds:%d" % (i % 3 + 1)}
                   for i in range(6)]
        themes = [{"theme_id": "payments_funds:%d" % k, "category": "payments_funds", "name": "n%d" % k, "size": 2,
                   "review_count": 2, "status": "emerging", "samples": ["s%d" % k]} for k in (1, 2, 3)]
        reply = {"groups": [{"name": "Withdrawal delays", "cluster_ids": ["c1", "c2"]}, {"name": "x", "cluster_ids": ["c3"]}]}
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: groq_ok(reply), sleep=lambda s: None)
        new, rep = theme_merge.merge_all(llm, "openai/gpt-oss-20b", aspects, themes, min_size=4)
        self.assertEqual(len(new), 2)
        big = new[0]
        self.assertEqual((big["name"], big["review_count"], big["merged_from"], big["status"]),
                         ("Withdrawal delays", 4, 2, "ranked"))
        self.assertEqual({a["theme_id"] for a in aspects}, {n["theme_id"] for n in new})
        self.assertAlmostEqual(theme_merge.coverage(aspects, new), 4 / 6)

    def test_single_cluster_category_needs_no_model_call(self):
        from voc import theme_merge
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        calls = []
        llm = LLM(d + "/c.db", groq_post=lambda u, h, b: calls.append(1) or groq_ok({"groups": []}), sleep=lambda s: None)
        out, rep = theme_merge.merge_category(llm, "m", "crash_bug", [{"review_count": 1, "samples": ["x"], "name": "x"}])
        self.assertEqual((calls, rep), ([], {"skipped": True}))


class ExternalImportTests(unittest.TestCase):
    def load(self):
        import importlib.util
        p = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "import_external_labels.py"
        spec = importlib.util.spec_from_file_location("imp_ext", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_find_labels_ignores_fences_commentary_and_reads_arrays(self):
        m = self.load()
        text = 'Sure! Here you go:\n```json\n{"reviewId": "a", "x": 1}\n```\nthen {"not": "a label"}\n' \
               '[{"reviewId": "b"}, {"reviewId": "c"}] done'
        self.assertEqual([x["reviewId"] for x in m.find_labels(text)], ["a", "b", "c"])

    def test_end_to_end_import_derives_severity_and_flags_bad_quotes(self):
        import subprocess
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(d + "/chunks")
        os.makedirs(d + "/returned")
        rv = [{"reviewId": "r1", "content": "my withdrawal is stuck for two days", "score": 1},
              {"reviewId": "r2", "content": "login keeps failing today", "score": 1}]
        with open(d + "/chunks/chunk_01.jsonl", "w") as f:
            for r in rv:
                f.write(json.dumps(r) + "\n")
        ok = {"reviewId": "r1", "usable": True, "overall_sentiment": "negative", "aspects": [
            {"category": "payments_funds", "aspect": "withdrawal stuck", "sentiment": "negative",
             "quote": "withdrawal is stuck", "impact": flags(money_blocked=True, event_described=True)}]}
        bad = {"reviewId": "r2", "usable": True, "overall_sentiment": "negative", "aspects": [
            {"category": "login_kyc_account", "aspect": "login fails", "sentiment": "negative",
             "quote": "login is failing", "impact": flags(core_action_blocked=True)}]}  # quote not in review
        open(d + "/returned/reply.txt", "w").write("```\n" + json.dumps(ok) + "\n" + json.dumps(bad) + "\n```")
        script = str(pathlib.Path(__file__).resolve().parent.parent / "scripts" / "import_external_labels.py")
        res = subprocess.run([sys.executable, "-I", script, "--chunks", d + "/chunks", "--returned", d + "/returned",
                              "--out", d + "/out.jsonl", "--labeler", "TestGPT"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        lines = [json.loads(l) for l in open(d + "/out.jsonl")]
        self.assertEqual(len(lines), 1)
        self.assertEqual((lines[0]["aspects"][0]["severity"], lines[0]["source"]), ("critical", "TestGPT"))
        self.assertIn("REDO THESE", res.stdout)
        self.assertIn("quote not found", res.stdout)


if __name__ == "__main__":
    unittest.main()
