import unittest

from mcp.card_engine import ShareCardPayload, compose_share_card_html


def _make_card(**overrides) -> ShareCardPayload:
    payload = ShareCardPayload(
        material_type="social",
        surface="social share card",
        entity_type="prompt",
        source_url="https://example.com/prompts/test",
        source_domain="example.com",
        page_title="Example Prompt",
        headline="Example Prompt",
        subhead="Structured prompt systems for agents.",
        cta="Open prompt",
        logo_path="/tmp/logo.svg",
        proof_title="Prompt Coverage",
        proof_meta=["Governed", "Production"],
        proof_excerpt="Proof excerpt text for the rendered share card.",
        proof_row="CID: bafkexample",
        proof_crop_path="/tmp/proof.png",
        proof_weight_guidance="Keep proof legible.",
        support_crop_path="/tmp/proof.png",
    )
    for key, value in overrides.items():
        setattr(payload, key, value)
    return payload


class CardEngineOverhaulTests(unittest.TestCase):
    def test_skip_proof_removes_all_proof_divs(self):
        card = _make_card(skip_proof=True)

        html = compose_share_card_html(card, material_type=card.material_type, asset_names={})

        self.assertNotIn('class="proof"', html)

    def test_dark_mode_uses_dark_palette_values(self):
        card = _make_card(dark_mode=True)

        html = compose_share_card_html(card, material_type=card.material_type, asset_names={})

        self.assertIn("--cream:#1a1a1e", html)
        self.assertIn("--ink:#f4ebd9", html)
        self.assertIn("--line:rgba(244,235,217,.10)", html)
        self.assertIn("color:rgba(244,235,217,.68)", html)
        self.assertIn("background:rgba(255,255,255,.06)", html)
        self.assertIn("background:rgba(244,235,217,.08)", html)
        self.assertIn("color:rgba(244,235,217,.52)", html)

    def test_logo_css_uses_transparent_tile_and_unconstrained_image(self):
        card = _make_card()

        html = compose_share_card_html(
            card,
            material_type=card.material_type,
            asset_names={"logo": "brand.svg"},
        )

        self.assertIn(".logo-tile { width:72px; height:72px; border-radius:20px; background:transparent;", html)
        self.assertNotIn(".logo-tile { width:72px; height:72px; border-radius:20px; background:var(--rust);", html)
        self.assertIn(".logo-img { width:100%; height:auto; max-height:100%; object-fit:contain; display:block; }", html)

    def test_share_card_payload_to_dict_includes_new_fields(self):
        card = _make_card(skip_proof=True, dark_mode=True)

        payload = card.to_dict()

        self.assertIn("skip_proof", payload)
        self.assertIn("dark_mode", payload)
        self.assertTrue(payload["skip_proof"])
        self.assertTrue(payload["dark_mode"])


if __name__ == "__main__":
    unittest.main()
