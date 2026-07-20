import base64
import json
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[2] / "content-production"
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts import images
from scripts.images import _generate_one_openai
class OpenAIImageProviderTests(unittest.TestCase):
    def setUp(self):
        self.transport = patch.object(images, "OPENAI_IMAGE_TRANSPORT", "curl")
        self.transport.start()
        self.addCleanup(self.transport.stop)

    def curl_result(self, stdout: bytes) -> SimpleNamespace:
        return SimpleNamespace(stdout=stdout, stderr=b"", returncode=0)

    def chat_response(self, content: str) -> bytes:
        encoded = content.split(",", 1)[1] if content.startswith("data:image/") else None
        if encoded is not None:
            return json.dumps({"data": [{"b64_json": encoded}]}).encode()
        if content.startswith("Image URL: "):
            return json.dumps({"data": [{"url": content.removeprefix("Image URL: ")}]}).encode()
        return json.dumps({"data": [{"b64_json": content}]}).encode()

    def test_decodes_data_url_from_chat_response(self):
        encoded = base64.b64encode(b"png-bytes").decode()
        with patch(
            "subprocess.run",
            return_value=self.curl_result(
                self.chat_response(f"data:image/png;base64,{encoded}")
            ),
        ):
            image_bytes, url = _generate_one_openai("A sunrise", "1024x768")
        self.assertEqual(image_bytes, b"png-bytes")
        self.assertIsNone(url)

    def test_downloads_url_with_second_curl_call(self):
        url = "https://example.com/generated.png"
        with patch(
            "subprocess.run",
            side_effect=[
                self.curl_result(self.chat_response(f"Image URL: {url}")),
                self.curl_result(b"image"),
            ],
        ) as run:
            image_bytes, returned_url = _generate_one_openai("A forest", "1024x768")
        self.assertEqual(image_bytes, b"image")
        self.assertEqual(returned_url, url)
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[1].args[0][-1], url)

    def test_rejects_response_without_image_data(self):
        with patch(
            "subprocess.run",
            return_value=self.curl_result(json.dumps({"data": [{}]}).encode()),
        ), self.assertRaisesRegex(RuntimeError, "neither base64 image data nor image URL"):
            _generate_one_openai("A forest", "1024x768")

    def test_provider_dispatch_keeps_existing_providers_isolated(self):
        with patch.object(images, "IMAGE_PROVIDER", "openai"), \
             patch.object(images, "OPENAI_API_KEY", "test-key"):
            self.assertIs(images._resolve_provider(), images._generate_one_openai)

        with patch.object(images, "IMAGE_PROVIDER", "agnes"), \
             patch.object(images, "IMAGE_API_KEY", "test-key"):
            self.assertIs(images._resolve_provider(), images._generate_one_agnes)

        with patch.object(images, "IMAGE_PROVIDER", "gemini"), \
             patch.object(images, "GEMINI_API_KEY", "test-key"):
            self.assertIs(images._resolve_provider(), images._generate_one_gemini)


if __name__ == "__main__":
    unittest.main()
