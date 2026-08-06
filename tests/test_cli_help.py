"""--help must work for every subcommand, document every flag, and state
the exit-code contract. Help text is the first thing a stranger reads."""

import contextlib
import io
import unittest

from agent_report_card.cli import main

SUBCOMMANDS = ["run", "demo", "init", "judge-check", "checks"]


def help_text(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        with self_exits():
            main(argv)
    return buffer.getvalue()


@contextlib.contextmanager
def self_exits():
    try:
        yield
    except SystemExit:
        pass


class TestHelp(unittest.TestCase):
    def test_top_level_help_shows_every_subcommand_and_a_worked_example(self):
        text = help_text(["--help"])
        for name in SUBCOMMANDS:
            self.assertIn(name, text)
        self.assertIn("demo --judge none", text)  # the no-keys entry point

    def test_every_subcommand_has_help(self):
        for name in SUBCOMMANDS:
            text = help_text([name, "--help"])
            self.assertIn("usage:", text, name)
            self.assertIn("-h, --help", text, name)

    def test_run_help_documents_every_flag(self):
        text = help_text(["run", "--help"])
        for flag in ["--tests", "--endpoint", "--judge", "--out", "--scores",
                     "--html", "--timeout", "--judge-timeout", "--limit", "--tags",
                     "--verbose"]:
            self.assertIn(flag, text, flag)
        # no flag may be listed without a description
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("--") and " " not in stripped:
                self.fail(f"flag documented with no help text: {stripped}")

    def test_run_help_states_the_exit_code_contract(self):
        text = help_text(["run", "--help"])
        self.assertIn("exit codes", text)
        for code in ["0", "1", "2"]:
            self.assertIn(code, text)

    def test_no_stray_percent_escapes_leak_into_help(self):
        for name in SUBCOMMANDS:
            self.assertNotIn("%%", help_text([name, "--help"]), name)


if __name__ == "__main__":
    unittest.main()
