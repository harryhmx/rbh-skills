import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[2] / "content-production"
if str(SKILL_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILL_ROOT))

from scripts.common import load_segments_json


class LoadSegmentsJsonTests(unittest.TestCase):
    def load(self, data, media_type="image"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "media-segments.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_segments_json(path, media_type)

    def test_accepts_each_media_type_and_combined_fields(self):
        combined = {
            "segments": [{
                "index": 0,
                "title": "Scene",
                "image_prompt": "An image",
                "video_prompt": "A video",
                "text": "Speech",
            }]
        }
        for media_type in ("image", "video", "speech"):
            with self.subTest(media_type=media_type):
                self.assertEqual(self.load(combined, media_type)[0]["index"], 0)

    def test_rejects_total_segments_and_unknown_fields(self):
        valid = {"segments": [{"index": 0, "title": "Scene", "image_prompt": "Prompt"}]}
        for data in (
            {"total_segments": 1, **valid},
            {"segments": [{**valid["segments"][0], "image_promt": "typo"}]},
        ):
            with self.subTest(data=data), self.assertRaisesRegex(ValueError, "unknown"):
                self.load(data)

    def test_rejects_invalid_containers(self):
        invalid = [
            [],
            {},
            {"segments": []},
            {"segments": "not-an-array"},
            {"segments": ["not-an-object"]},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.load(data)

    def test_rejects_invalid_common_fields(self):
        invalid_segments = [
            {"title": "Scene", "image_prompt": "Prompt"},
            {"index": True, "title": "Scene", "image_prompt": "Prompt"},
            {"index": -1, "title": "Scene", "image_prompt": "Prompt"},
            {"index": 0, "title": " ", "image_prompt": "Prompt"},
            {"index": 0, "title": "Scene", "image_prompt": " "},
        ]
        for segment in invalid_segments:
            with self.subTest(segment=segment), self.assertRaises(ValueError):
                self.load({"segments": [segment]})

    def test_requires_command_field(self):
        data = {"segments": [{"index": 0, "title": "Scene", "image_prompt": "Prompt"}]}
        with self.assertRaisesRegex(ValueError, "video_prompt"):
            self.load(data, "video")
        with self.assertRaisesRegex(ValueError, "text"):
            self.load(data, "speech")

    def test_rejects_duplicate_non_contiguous_and_unordered_indexes(self):
        for indexes in ([0, 0], [0, 2], [1, 0]):
            data = {
                "segments": [
                    {"index": index, "title": f"Scene {pos}", "image_prompt": "Prompt"}
                    for pos, index in enumerate(indexes)
                ]
            }
            with self.subTest(indexes=indexes), self.assertRaisesRegex(ValueError, "contiguous"):
                self.load(data)


if __name__ == "__main__":
    unittest.main()
