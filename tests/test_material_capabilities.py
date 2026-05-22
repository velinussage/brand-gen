"""Unit tests for the Material Capability Plugin Registry and Campaign Harness integration."""

import unittest
from typing import Any
from brand_gen.materials import (
    MaterialCapability,
    fetch_material_capability,
    list_capabilities,
    register,
)
from brand_gen.materials._registry import _REGISTRY
from brand_gen.material_prompt_profiles import (
    get_material_prompt_profile,
    normalize_material_profile_key,
)
from brand_gen.runtime_models import MATERIAL_CONFIG


class CustomTestCapability(MaterialCapability):
    def __init__(self, mat_type: str, prio: int = 50, default_model: str = "test-model"):
        self._material_type = mat_type
        self._priority = prio
        self._default_model = default_model

    @property
    def material_type(self) -> str:
        return self._material_type

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def default_model(self) -> str:
        return self._default_model

    @property
    def default_aspect_ratio(self) -> str:
        return "1:1"

    @property
    def prompt_profile(self) -> dict[str, Any]:
        return {
            "material_type": self._material_type,
            "job_to_be_done": "Test job",
            "default_model": self._default_model,
        }


class MaterialCapabilitiesTests(unittest.TestCase):
    def test_default_capabilities_are_registered(self):
        """Verify all 7 built-in plugins are automatically registered on import."""
        # Ensure they are registered
        capabilities = list_capabilities()
        material_types = {c.material_type for c in capabilities}
        
        expected_types = {
            "share_card",
            "browser_illustration",
            "logo",
            "banner",
            "video_shot",
            "poster",
            "brand_scene",
        }
        
        for t in expected_types:
            self.assertIsNotNone(
                fetch_material_capability(t),
                f"Built-in capability for {t} should be registered."
            )

    def test_priority_overrides(self):
        """Verify registration priority rules (higher overrides lower)."""
        test_type = "priority-test-mat"
        cap_low = CustomTestCapability(test_type, prio=10, default_model="low-model")
        cap_high = CustomTestCapability(test_type, prio=100, default_model="high-model")

        # Register low first
        register(cap_low)
        self.assertEqual(fetch_material_capability(test_type).default_model, "low-model")

        # Register high - should override since 100 > 10
        register(cap_high)
        self.assertEqual(fetch_material_capability(test_type).default_model, "high-model")

        # Try to register low again - should be ignored since 10 <= 100
        register(cap_low)
        self.assertEqual(fetch_material_capability(test_type).default_model, "high-model")

        # Clean up
        if test_type in _REGISTRY:
            del _REGISTRY[test_type]

    def test_raw_and_normalized_key_resolutions(self):
        """Verify capability resolves correctly under raw, normalized, and aliased keys."""
        # Get logo capability
        cap = fetch_material_capability("logo")
        self.assertIsNotNone(cap)

        # Check with different key formats
        self.assertEqual(fetch_material_capability("Logo"), cap)
        
        # Test custom key mapping (e.g. brand_scene -> illustrated-brand-world)
        cap_scene = fetch_material_capability("brand_scene")
        cap_world = fetch_material_capability("illustrated-brand-world")
        self.assertEqual(cap_scene, cap_world)

    def test_get_material_prompt_profile_uses_capabilities(self):
        """Verify prompt profile getter prioritizes capability-defined profiles."""
        test_type = "profile-override-mat"
        cap = CustomTestCapability(test_type, default_model="special-overridden-model")
        register(cap)

        profile = get_material_prompt_profile(test_type)
        self.assertIsNotNone(profile)
        self.assertEqual(profile.get("default_model"), "special-overridden-model")

        # Clean up
        if test_type in _REGISTRY:
            del _REGISTRY[test_type]

    def test_material_config_extension(self):
        """Verify dynamic extension of global MATERIAL_CONFIG when capability registers."""
        test_type = "config-extension-mat"
        cap = CustomTestCapability(test_type, default_model="dynamic-model")
        
        # Before registration, shouldn't be in MATERIAL_CONFIG (or if it is, we mock registration)
        if test_type in MATERIAL_CONFIG:
            del MATERIAL_CONFIG[test_type]
            
        register(cap)
        self.assertIn(test_type, MATERIAL_CONFIG)
        self.assertEqual(MATERIAL_CONFIG[test_type]["default_model"], "dynamic-model")

        # Clean up
        if test_type in _REGISTRY:
            del _REGISTRY[test_type]
        if test_type in MATERIAL_CONFIG:
            del MATERIAL_CONFIG[test_type]
