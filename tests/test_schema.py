import os
import tempfile
import unittest

from agent_report_card import scrub
from agent_report_card.schema import SchemaError, load_suite

GOOD = """\
suite: t
endpoint:
  response:
    answer: answer
    contexts: contexts.*.text
    sources: contexts.*.source
gates:
  min_accuracy: 0.9
corpus_manifest: [a.md]
cases:
  - id: q1
    question: What is x?
    expected: "42"
    match: number
  - id: q2
    question: Address?
    answerable: false
"""


def write(text):
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", delete=False, encoding="utf-8")
    handle.write(text)
    handle.close()
    return handle.name


class TestSchema(unittest.TestCase):
    def test_good_suite_loads(self):
        suite = load_suite(write(GOOD))
        self.assertEqual(suite.name, "t")
        self.assertEqual(len(suite.cases), 2)
        self.assertEqual(suite.cases[0].match, "number")
        self.assertTrue(suite.gates.explicit)
        self.assertEqual(suite.gates.min_accuracy, 0.9)
        self.assertFalse(suite.cases[1].answerable)
        self.assertEqual(len(suite.sha256), 64)

    def test_unknown_key_names_line_and_fix(self):
        bad = GOOD.replace("    match: number", "    match: number\n    exspected: y")
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        message = str(ctx.exception)
        self.assertIn("exspected", message)
        self.assertIn("line", message)
        self.assertIn("allowed keys", message)

    def test_duplicate_id(self):
        bad = GOOD.replace("id: q2", "id: q1")
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        self.assertIn("duplicate", str(ctx.exception))

    def test_unanswerable_with_expected_contradiction(self):
        bad = GOOD + "    expected: nope\n"
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        self.assertIn("answerable: false", str(ctx.exception))

    def test_match_without_expected(self):
        bad = GOOD.replace('    expected: "42"\n', "")
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        self.assertIn("needs an expected answer", str(ctx.exception))

    def test_expected_defaults_to_judge_route(self):
        text = GOOD.replace("    match: number", "")
        suite = load_suite(write(text))
        self.assertEqual(suite.cases[0].match, "judge")

    def test_unset_env_var_fails_fast_and_names_only_the_var(self):
        bad = GOOD.replace(
            "endpoint:\n",
            "endpoint:\n  headers:\n    Authorization: Bearer ${ARC_MISSING_VAR}\n")
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        self.assertIn("ARC_MISSING_VAR", str(ctx.exception))

    def test_invalid_regexes_fail_at_load_time(self):
        bad_expected = GOOD.replace('    expected: "42"\n    match: number',
                                    '    expected: "TCK-(\\\\d{4}"\n    match: regex')
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad_expected))
        self.assertIn("not a valid regex", str(ctx.exception))
        bad_needle = GOOD.replace(
            "    match: number",
            "    match: number\n    must_contain: [\"/bad(regex/\"]")
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad_needle))
        self.assertIn("not a valid regex", str(ctx.exception))

    def test_endpoint_path_must_start_with_slash(self):
        # a path like '@evil.example/ask' would turn the user's host into
        # URL userinfo and send the request (with headers) elsewhere
        bad = GOOD.replace("endpoint:\n",
                           "endpoint:\n  path: \"@evil.example/ask\"\n")
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        self.assertIn("must start with '/'", str(ctx.exception))

    def test_match_contains_requires_must_contain(self):
        bad = GOOD.replace("    match: number", "    match: contains")
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        self.assertIn("must_contain", str(ctx.exception))

    def test_response_mapping_defaults_and_explicit_null(self):
        suite = load_suite(write(GOOD.replace(
            "endpoint:\n  response:\n    answer: answer\n"
            "    contexts: contexts.*.text\n    sources: contexts.*.source\n",
            "")))
        self.assertEqual(suite.endpoint.contexts_path, "contexts.*.text")
        self.assertEqual(suite.endpoint.sources_path, "contexts.*.source")
        disabled = GOOD.replace("    contexts: contexts.*.text",
                                "    contexts: null")
        self.assertIsNone(load_suite(write(disabled)).endpoint.contexts_path)

    def test_init_starter_yaml_validates(self):
        from agent_report_card.cli import STARTER_YAML
        suite = load_suite(write(STARTER_YAML))
        self.assertEqual(len(suite.cases), 4)
        self.assertEqual(suite.cases[2].match, "regex")

    def test_json_suite_loads_with_same_validation(self):
        # JSON is a subset of YAML, so a .json test file goes through the
        # same loader and the same strict validation.
        import json as jsonlib
        suite_json = {"suite": "j", "cases": [
            {"id": "j1", "question": "x?", "expected": "42", "match": "number"}]}
        path = write(jsonlib.dumps(suite_json))
        suite = load_suite(path)
        self.assertEqual(suite.cases[0].match, "number")
        bad = jsonlib.dumps({"suite": "j", "cases": [
            {"id": "j1", "question": "x?", "exspected": "42"}]})
        with self.assertRaises(SchemaError) as ctx:
            load_suite(write(bad))
        self.assertIn("exspected", str(ctx.exception))

    def test_set_env_var_expands_and_registers_for_scrub(self):
        scrub.reset()
        os.environ["ARC_TEST_TOKEN"] = "sk-veryverysecret"
        try:
            text = GOOD.replace(
                "endpoint:\n",
                "endpoint:\n  headers:\n    Authorization: Bearer ${ARC_TEST_TOKEN}\n")
            suite = load_suite(write(text))
            self.assertEqual(suite.endpoint.expanded_headers["Authorization"],
                             "Bearer sk-veryverysecret")
            cleaned = scrub.scrub("the token sk-veryverysecret leaked")
            self.assertNotIn("sk-veryverysecret", cleaned)
            self.assertIn("${ARC_TEST_TOKEN}", cleaned)
        finally:
            del os.environ["ARC_TEST_TOKEN"]
            scrub.reset()


if __name__ == "__main__":
    unittest.main()
