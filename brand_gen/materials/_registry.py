"""Material Capability Plugin Registry.

Defines the pluggable Material Capability model and priority-based registry.
"""
from __future__ import annotations

import abc
from abc import ABC, abstractmethod
from typing import Any

class MaterialCapability(ABC):
    """Abstract base class representing a material generation capability."""

    @property
    @abstractmethod
    def material_type(self) -> str:
        """The canonical material type identifier (e.g. 'share_card', 'logo')."""
        pass

    @property
    def priority(self) -> int:
        """Registration priority. Higher priority overrides lower priority."""
        return 50

    @property
    @abstractmethod
    def default_model(self) -> str:
        """The default model used for generation."""
        pass

    @property
    @abstractmethod
    def default_aspect_ratio(self) -> str:
        """The default aspect ratio (e.g., '1:1', '16:9')."""
        pass

    @property
    def generation_mode(self) -> str:
        """The generation mode, e.g. 'image' or 'video'."""
        return "image"

    @property
    def default_render_backend(self) -> str:
        """The default render backend, e.g. 'native' or 'html'."""
        return "native"

    @property
    @abstractmethod
    def prompt_profile(self) -> dict[str, Any]:
        """The prompt profile dictionary for this capability."""
        pass

    def build_prompts(self, context: dict[str, Any]) -> dict[str, Any]:
        """Hook to build prompts or return custom prompt overrides.

        Returns empty dict by default to signal the standard agent flow should run.
        """
        return {}

    def validate_artifact(self, artifact_path: str, context: dict[str, Any]) -> list[str]:
        """Validate the generated artifact. Returns a list of validation error strings."""
        return []

    @property
    def critic_overrides(self) -> list[str] | None:
        """Optional list of critic agent roles to run in the critique panel."""
        return None

    def export(self, artifact_path: str, context: dict[str, Any]) -> dict[str, Any]:
        """Hook to handle post-generation exports."""
        return {"exported_path": artifact_path}


_REGISTRY: dict[str, MaterialCapability] = {}


def register(capability: MaterialCapability) -> None:
    """Register a MaterialCapability and dynamically extend the global MATERIAL_CONFIG."""
    material_type = capability.material_type
    
    try:
        from brand_gen.material_prompt_profiles import normalize_material_profile_key
        norm_key = normalize_material_profile_key(material_type)
    except Exception:
        norm_key = material_type.strip().lower().replace("_", "-")

    # Check priority if already registered under raw key
    if material_type in _REGISTRY:
        existing = _REGISTRY[material_type]
        if capability.priority <= existing.priority:
            return  # Existing has higher or equal priority, skip
            
    _REGISTRY[material_type] = capability
    if norm_key != material_type:
        _REGISTRY[norm_key] = capability

    # Dynamically inject/extend the global MATERIAL_CONFIG
    try:
        from brand_gen.runtime_models import MATERIAL_CONFIG
        config_entry = {
            "default_model": capability.default_model,
            "default_aspect_ratio": capability.default_aspect_ratio,
            "generation_mode": capability.generation_mode,
            "default_render_backend": capability.default_render_backend,
        }
        MATERIAL_CONFIG[material_type] = config_entry
        if norm_key != material_type:
            MATERIAL_CONFIG[norm_key] = config_entry
    except Exception as exc:
        # Avoid import errors during initialization/bootstrapping
        pass


def fetch_material_capability(material_type: str | None) -> MaterialCapability | None:
    """Retrieve the registered MaterialCapability for the given material type."""
    if not material_type:
        return None
    from brand_gen.material_prompt_profiles import normalize_material_profile_key
    key = normalize_material_profile_key(material_type)
    return _REGISTRY.get(key)


def list_capabilities() -> list[MaterialCapability]:
    """List all registered material capabilities sorted by material type."""
    return sorted(_REGISTRY.values(), key=lambda c: c.material_type)
