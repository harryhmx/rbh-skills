import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SKILL_ROOT = Path(__file__).resolve().parents[2] / "content-production"
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts import videos


class VideoResultTests(unittest.TestCase):
    def test_poll_returns_provider_failures(self):
        pending = {"failed-id": {"index": 0, "title": "Failed"}}
        with patch.object(videos, "_get_video", return_value={"status": "failed"}):
            completed, failed = videos._poll_all_videos(pending, timeout=1, interval=0)
        self.assertEqual(completed, {})
        self.assertIn("failed-id", failed)

    def test_poll_returns_timeouts(self):
        pending = {"slow-id": {"index": 0, "title": "Slow"}}
        with patch.object(videos.time, "time", side_effect=[0, 2]):
            completed, failed = videos._poll_all_videos(pending, timeout=1, interval=0)
        self.assertEqual(completed, {})
        self.assertIn("Timed out", failed["slow-id"])

    def test_generate_videos_keeps_mixed_success_and_failure(self):
        segments = [
            {"index": 0, "title": "Success", "video_prompt": "Success prompt"},
            {"index": 1, "title": "Failure", "video_prompt": "Failure prompt"},
        ]

        def submit(payload):
            return {"id": "success-id" if payload["prompt"] == "Success prompt" else "failure-id"}

        def poll(pending, timeout, interval, on_completed=None):
            on_completed("success-id", {"status": "completed", "url": "https://example/video.mp4"})
            pending.clear()
            return {"success-id": {"status": "completed"}}, {"failure-id": "Timed out after 900s"}

        response = unittest.mock.Mock(content=b"x" * 10000)
        response.raise_for_status.return_value = None

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(videos, "VIDEO_API_KEY", "test-key"), \
             patch.object(videos, "VIDEO_PROVIDER", "agnes"), \
             patch.object(videos, "_agnes_video_request", side_effect=submit), \
             patch.object(videos, "_poll_all_videos", side_effect=poll), \
             patch.object(videos.http_requests, "get", return_value=response), \
             patch.object(videos.time, "sleep"):
            results = videos.generate_videos(segments, output_dir=tmp)

        self.assertEqual(len(results), 2)
        self.assertIsNotNone(results[0]["file_path"])
        self.assertEqual(results[1]["error"], "Timed out after 900s")
        self.assertEqual([result["index"] for result in results], [0, 1])


if __name__ == "__main__":
    unittest.main()
