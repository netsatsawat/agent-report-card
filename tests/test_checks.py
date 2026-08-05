"""Table-driven tests for every deterministic check, including Thai-script
fixtures for the substring, number, and length checks."""

import unittest

from agent_report_card.checks_code import (extract_numbers, normalize,
                                           run_code_checks)
from agent_report_card.client import EndpointReply
from agent_report_card.schema import Case, Patterns, Suite, EndpointCfg, Gates


def make_suite(manifest=(), patterns=None):
    return Suite(name="t", path="t.yaml", sha256="0" * 64,
                 endpoint=EndpointCfg(), judge_model=None, gates=Gates(),
                 patterns=patterns or Patterns(),
                 corpus_manifest=list(manifest), cases=[])


def make_case(**kw):
    defaults = dict(id="c", question="q", line=1)
    defaults.update(kw)
    return Case(**defaults)


def status(results, name):
    return next(c.status for c in results if c.name == name)


def run(case, reply, suite=None):
    return run_code_checks(case, reply, suite or make_suite())


class TestNormalization(unittest.TestCase):
    def test_number_canonicalization(self):
        for text, expect in [("1,500 THB", [1500.0]), ("THB1500", [1500.0]),
                             ("3.2%", [3.2]), ("THB 0.85 per share", [0.85]),
                             ("87% and 214 stores", [87.0, 214.0])]:
            self.assertEqual(extract_numbers(text), expect, text)

    def test_ranges_dates_and_lists_are_not_negatives(self):
        for text, expect in [
                ("growth over 2019-2024", [2019.0, 2024.0]),
                ("dated 2026-08-05", [2026.0, 8.0, 5.0]),
                ("options 5,6 are valid", [5.0, 6.0]),
                ("ticket TCK-42", [42.0]),
                ("it was -5 degrees", [-5.0]),
                ("x=-5", [-5.0])]:
            self.assertEqual(extract_numbers(text), expect, text)

    def test_typographic_apostrophes_normalize(self):
        self.assertEqual(normalize("I can’t “help” with that"),
                         "i can't \"help\" with that")

    def test_normalize_thai_nfc_and_case(self):
        self.assertEqual(normalize("  ค่า​ปรับ  A  B  ".replace("​", "")),
                         "ค่าปรับ a b")


class TestChecks(unittest.TestCase):
    def test_answered_fail_on_error_and_empty(self):
        case = make_case()
        self.assertEqual(status(run(case, EndpointReply(error="HTTP 500")),
                                "answered"), "fail")
        self.assertEqual(status(run(case, EndpointReply(answer="  ")),
                                "answered"), "fail")
        self.assertEqual(status(run(case, EndpointReply(answer="hi")),
                                "answered"), "pass")

    def test_exact_match(self):
        case = make_case(expected="42 Baht", match="exact")
        self.assertEqual(status(run(case, EndpointReply(answer="  42  baht ")),
                                "exact_match"), "pass")
        self.assertEqual(status(run(case, EndpointReply(answer="43 baht")),
                                "exact_match"), "fail")

    def test_contains_all_english_and_thai(self):
        case = make_case(must_contain=["Asia Pass", "ค่าปรับ"])
        ok = EndpointReply(answer="The asia pass costs more; ค่าปรับคือ 1,500 บาท")
        self.assertEqual(status(run(case, ok), "contains_all"), "pass")
        missing = EndpointReply(answer="The asia pass costs more")
        self.assertEqual(status(run(case, missing), "contains_all"), "fail")

    def test_contains_none_and_regex_needle(self):
        case = make_case(must_not_contain=["599", "/9\\d% uptime/"])
        self.assertEqual(status(run(case, EndpointReply(answer="THB 599")),
                                "contains_none"), "fail")
        self.assertEqual(status(run(case, EndpointReply(answer="99% uptime")),
                                "contains_none"), "fail")
        self.assertEqual(status(run(case, EndpointReply(answer="THB 649")),
                                "contains_none"), "pass")

    def test_numbers_agree_currency_and_thousands(self):
        case = make_case(expected="1,500 THB", match="number")
        for good in ["1500 baht", "THB1,500", "the fee is 1,500"]:
            self.assertEqual(status(run(case, EndpointReply(answer=good)),
                                    "numbers_agree"), "pass", good)
        self.assertEqual(status(run(case, EndpointReply(answer="2,000 THB")),
                                "numbers_agree"), "fail")

    def test_numbers_agree_tolerance_and_thai_baht_text(self):
        case = make_case(expected="ค่าปรับ 1,500 บาท", match="number",
                         tolerance=1.0)
        self.assertEqual(status(run(case, EndpointReply(answer="ประมาณ 1500.5 บาท")),
                                "numbers_agree"), "pass")
        self.assertEqual(status(run(case, EndpointReply(answer="1,600 บาท")),
                                "numbers_agree"), "fail")

    def test_numbers_agree_na_when_expected_has_no_digits(self):
        case = make_case(expected="It depends on the plan tier",
                         match="number")
        self.assertEqual(status(run(case, EndpointReply(answer="anything")),
                                "numbers_agree"), "na")

    def test_regex_match(self):
        case = make_case(expected=r"TCK-\d{4}", match="regex")
        self.assertEqual(status(run(case, EndpointReply(answer="see TCK-1234")),
                                "regex_match"), "pass")
        self.assertEqual(status(run(case, EndpointReply(answer="see TCK-12")),
                                "regex_match"), "fail")

    def test_citation_checks(self):
        suite = make_suite(manifest=["plans_2026.md", "hr_policy.md"])
        case = make_case(expected_sources=["plans_2026.md"])
        good = EndpointReply(answer="x", sources=["plans_2026.md"],
                             contexts=["ctx"])
        self.assertEqual(status(run(case, good, suite),
                                "cites_expected_source"), "pass")
        self.assertEqual(status(run(case, good, suite),
                                "no_phantom_citation"), "pass")
        phantom = EndpointReply(answer="x", sources=["ghost.md"],
                                contexts=["ctx"])
        self.assertEqual(status(run(case, phantom, suite),
                                "cites_expected_source"), "fail")
        self.assertEqual(status(run(case, phantom, suite),
                                "no_phantom_citation"), "fail")
        no_manifest = make_suite()
        self.assertEqual(status(run(case, phantom, no_manifest),
                                "no_phantom_citation"), "na")

    def test_retrieval_hit_localization(self):
        case = make_case(must_contain=["live chat"])
        hit = EndpointReply(answer="only call center",
                            contexts=["We offer live chat 08:00 to 22:00"])
        self.assertEqual(status(run(case, hit), "retrieval_hit"), "pass")
        miss = EndpointReply(answer="only call center",
                             contexts=["Unrelated pricing text"])
        self.assertEqual(status(run(case, miss), "retrieval_hit"), "fail")
        no_ctx = EndpointReply(answer="only call center")
        self.assertEqual(status(run(case, no_ctx), "retrieval_hit"), "na")

    def test_retrieval_hit_with_only_expected_sources(self):
        case = make_case(expected_sources=["hr_policy.md"])
        by_name_in_ctx = EndpointReply(
            answer="x", contexts=["[hr_policy.md] parental leave is 30 days"])
        self.assertEqual(status(run(case, by_name_in_ctx), "retrieval_hit"),
                         "pass")
        wrong_doc = EndpointReply(
            answer="x", contexts=["[pricing.md] the 5G add-on costs 649"])
        self.assertEqual(status(run(case, wrong_doc), "retrieval_hit"),
                         "fail")

    def test_source_matching_is_case_insensitive(self):
        suite = make_suite(manifest=["Plans_2026.md"])
        case = make_case(expected_sources=["PLANS_2026.md"])
        reply = EndpointReply(answer="x", sources=["plans_2026.MD"],
                              contexts=["ctx"])
        self.assertEqual(status(run(case, reply, suite),
                                "cites_expected_source"), "pass")
        self.assertEqual(status(run(case, reply, suite),
                                "no_phantom_citation"), "pass")

    def test_no_error_leak_builtin_and_suite_patterns(self):
        suite = make_suite(patterns=Patterns(leak_markers=["You are HelperBot"]))
        case = make_case()
        for bad in ["Traceback (most recent call last): boom",
                    "You are HelperBot, a helpful assistant"]:
            self.assertEqual(status(run(case, EndpointReply(answer=bad), suite),
                                    "no_error_leak"), "fail", bad)
        self.assertEqual(status(run(case, EndpointReply(answer="all good"), suite),
                                "no_error_leak"), "pass")

    def test_refusal_checks_english_and_thai_patterns(self):
        thai = Patterns(refusal=["ไม่สามารถให้ข้อมูล"])
        suite = make_suite(patterns=thai)
        oob = make_case(answerable=False)
        refusal_en = EndpointReply(answer="I can't share that information.")
        refusal_curly = EndpointReply(answer="I can’t share that information.")
        refusal_th = EndpointReply(answer="ขออภัย ไม่สามารถให้ข้อมูลส่วนบุคคลได้")
        answer = EndpointReply(answer="The director earns 3.4 million.")
        self.assertEqual(status(run(oob, refusal_en, suite),
                                "refuses_when_required"), "pass")
        self.assertEqual(status(run(oob, refusal_curly, suite),
                                "refuses_when_required"), "pass")
        self.assertEqual(status(run(oob, refusal_th, suite),
                                "refuses_when_required"), "pass")
        self.assertEqual(status(run(oob, answer, suite),
                                "refuses_when_required"), "fail")
        ok_case = make_case()
        self.assertEqual(status(run(ok_case, refusal_th, suite),
                                "answers_when_it_should"), "fail")
        self.assertEqual(status(run(ok_case, answer, suite),
                                "answers_when_it_should"), "pass")

    def test_length_in_bounds_thai_text(self):
        case = make_case(max_chars=10)
        self.assertEqual(status(run(case, EndpointReply(answer="ค่าปรับ 1500")),
                                "length_in_bounds"), "fail")
        self.assertEqual(status(run(case, EndpointReply(answer="ค่าปรับ")),
                                "length_in_bounds"), "pass")

    def test_latency_under(self):
        case = make_case(budget_seconds=0.15)
        slow = EndpointReply(answer="x", latency_s=0.3)
        fast = EndpointReply(answer="x", latency_s=0.1)
        self.assertEqual(status(run(case, slow), "latency_under"), "fail")
        self.assertEqual(status(run(case, fast), "latency_under"), "pass")
        no_budget = make_case()
        self.assertEqual(status(run(no_budget, fast), "latency_under"), "na")


if __name__ == "__main__":
    unittest.main()
