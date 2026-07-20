import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2] / "content-production"
CLI = SKILL_ROOT / "scripts" / "cli.py"


class CliContractTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_video_help_uses_config_defaults_and_has_no_prompt_key(self):
        result = self.run_cli("video", "--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("1152x768", result.stdout)
        self.assertIn("121", result.stdout)
        self.assertIn("24", result.stdout)
        self.assertNotIn("prompt-key", result.stdout)

    def test_argument_validators_reject_bad_values(self):
        cases = [
            ("image", "--size", "1x0"),
            ("video", "--size", "abcxdef"),
            ("video", "--num-frames", "120"),
            ("video", "--frame-rate", "61"),
        ]
        for command, flag, value in cases:
            with self.subTest(command=command, flag=flag, value=value):
                result = self.run_cli(command, "-i", "unused.json", flag, value)
                self.assertEqual(result.returncode, 2)

    def test_schema_error_exits_two_before_provider_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "ordinary.json"
            input_path.write_text('{"title": "ordinary JSON"}', encoding="utf-8")
            result = self.run_cli("image", "-i", str(input_path), "-o", str(Path(tmp) / "out"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("top-level", result.stderr)
            self.assertNotIn("API_KEY", result.stderr)
            self.assertFalse((Path(tmp) / "out").exists())


if __name__ == "__main__":
    unittest.main()
