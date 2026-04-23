import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen.vlm_critique import run_vlm_critique, run_vlm_json


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class VlmCritiqueTests(unittest.TestCase):
    def test_run_vlm_json_uses_openrouter_key_and_normalizes_model_name(self):
        calls = []

        def fake_post(url, headers=None, json=None, timeout=None):
            calls.append({"url": url, "headers": headers or {}, "json": json or {}, "timeout": timeout})
            return _FakeResponse(
                {
                    "choices": [
                        {
                            "message": {
                                "content": '{"approved": true, "p1": []}'
                            }
                        }
                    ]
                }
            )

        fake_httpx = types.SimpleNamespace(post=fake_post)

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"
            image_path.write_bytes(b"fake-png")

            with patch.dict("sys.modules", {"httpx": fake_httpx}):
                result = run_vlm_json(
                    image_path,
                    "Return JSON",
                    "Describe this image",
                    env={
                        "OPENROUTER_API_KEY": "openrouter-key",
                        "BRAND_GEN_VLM_MODEL": "openrouter/google/gemini-2.5-flash",
                    },
                )

        self.assertEqual(result["vlm_provider"], "openrouter")
        self.assertEqual(result["vlm_model"], "google/gemini-2.5-flash")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["url"], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer openrouter-key")
        self.assertEqual(calls[0]["json"]["model"], "google/gemini-2.5-flash")
        self.assertEqual(calls[0]["json"]["messages"][1]["content"][0]["type"], "text")
        self.assertEqual(calls[0]["json"]["messages"][1]["content"][1]["type"], "image_url")

    def test_run_vlm_critique_stub_mentions_openrouter_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "sample.png"
            image_path.write_bytes(b"fake-png")

            with patch("brand_gen.vlm_critique.run_vlm_json", return_value=None):
                result = run_vlm_critique(image_path, "Check alignment", {})

        self.assertFalse(result["vlm_available"])
        self.assertIn("OPENROUTER_API_KEY", result["vlm_unavailable_reason"])
        self.assertNotIn("OPENAI_API_KEY", result["vlm_unavailable_reason"])


if __name__ == "__main__":
    unittest.main()
