import base64
import http.client
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from brand_gen import generate


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class GenerateTransportTests(unittest.TestCase):
    def test_build_input_coerces_gpt_image_2_aspect_ratio_and_applies_defaults(self):
        model_config = generate.MODELS["image"]["gpt-image-2"]
        args = type(
            "Args",
            (),
            {
                "model": "gpt-image-2",
                "prompt": "Make a product visual",
                "preset": None,
                "negative_prompt": None,
                "base_image": None,
                "image": None,
                "reference_tag": None,
                "motion_reference": None,
                "width": None,
                "height": None,
                "aspect_ratio": "4:5",
                "resolution": None,
                "guidance_scale": None,
                "steps": None,
                "seed": None,
                "duration": None,
                "motion_mode": None,
                "character_orientation": None,
                "keep_original_sound": False,
                "style": None,
            },
        )()

        with patch("sys.stderr") as mock_stderr:
            input_data = generate.build_input(model_config, args, "image")

        self.assertEqual(input_data["aspect_ratio"], "2:3")
        self.assertEqual(input_data["quality"], "high")
        self.assertEqual(input_data["background"], "auto")
        self.assertEqual(input_data["output_format"], "png")
        self.assertIn("does not support aspect ratio '4:5'", "".join(call.args[0] for call in mock_stderr.write.call_args_list))

    def test_normalize_model_aspect_ratio_keeps_supported_gpt_image_2_ratio(self):
        model_config = generate.MODELS["image"]["gpt-image-2"]
        self.assertEqual(
            generate.normalize_model_aspect_ratio("gpt-image-2", model_config, "3:2"),
            "3:2",
        )

    def test_replace_data_uris_with_uploads_handles_nested_lists_and_dicts(self):
        data_uri = "data:image/png;base64," + base64.b64encode(b"png-bytes").decode()

        uploaded_paths = []

        def fake_upload(_token, file_path):
            uploaded_paths.append(Path(file_path).suffix)
            return f"https://files.example/{len(uploaded_paths)}"

        with patch("brand_gen.generate.upload_file_to_replicate", side_effect=fake_upload):
            replaced = generate._replace_data_uris_with_uploads(
                "token",
                {
                    "prompt": "hello",
                    "input_images": [data_uri, data_uri],
                    "metadata": {"cover": data_uri},
                },
            )

        self.assertEqual(
            replaced,
            {
                "prompt": "hello",
                "input_images": [
                    "https://files.example/1",
                    "https://files.example/2",
                ],
                "metadata": {"cover": "https://files.example/3"},
            },
        )
        self.assertEqual(uploaded_paths, [".png", ".png", ".png"])

    def test_create_prediction_retries_with_uploaded_nested_data_uris(self):
        data_uri = "data:image/png;base64," + base64.b64encode(b"png-bytes").decode()
        requests = []
        responses = [
            http.client.RemoteDisconnected("dropped"),
            _FakeResponse({"status": "succeeded", "output": "https://out.example/image.png"}),
        ]

        def fake_urlopen(req, timeout=0):
            requests.append(req)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        with (
            patch("brand_gen.generate.upload_file_to_replicate", return_value="https://files.example/uploaded.png"),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            result = generate.create_prediction(
                "token",
                "owner/model",
                {"prompt": "hello", "input_images": [data_uri]},
            )

        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(len(requests), 2)
        retried_payload = json.loads(requests[1].data.decode())
        self.assertEqual(
            retried_payload,
            {
                "input": {
                    "prompt": "hello",
                    "input_images": ["https://files.example/uploaded.png"],
                }
            },
        )

