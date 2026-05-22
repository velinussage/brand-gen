"""Material Capability Package.

Auto-registers all built-in capability plugins on import.
"""
from __future__ import annotations

from brand_gen.materials._registry import (
    MaterialCapability,
    fetch_material_capability,
    list_capabilities,
    register,
)

# Import capability modules to trigger auto-registration
from brand_gen.materials.share_card import capability as _share_card
from brand_gen.materials.browser_illustration import capability as _browser_illustration
from brand_gen.materials.logo import capability as _logo
from brand_gen.materials.banner import capability as _banner
from brand_gen.materials.video_shot import capability as _video_shot
from brand_gen.materials.poster import capability as _poster
from brand_gen.materials.brand_scene import capability as _brand_scene

__all__ = [
    "MaterialCapability",
    "fetch_material_capability",
    "list_capabilities",
    "register",
]
