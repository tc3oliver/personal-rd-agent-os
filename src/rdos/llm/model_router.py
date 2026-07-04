"""Model router — picks a model profile given task/risk/privacy.

Returns a `ModelRoutingDecision` (data only). NEVER returns a pre-bound
tool model — that's a deliberate non-goal so adapters stay swappable.
"""

from __future__ import annotations

from dataclasses import dataclass

from rdos.config import ModelsConfig, ProfileConfig
from rdos.schemas.privacy import PrivacyLevel
from rdos.schemas.routing import ModelRoutingDecision

# Tasks the router knows about by default
KNOWN_TASKS = {
    "research_memory",
    "research_synthesis",
    "daily_digest",
    "technical_writing",
    "code_analysis",
}


@dataclass
class RoutingInput:
    task_type: str
    effective_privacy_level: PrivacyLevel
    risk_level: str = "low"  # low | medium | high


class ModelRouter:
    def __init__(self, models: ModelsConfig) -> None:
        self.models = models

    def select(self, inp: RoutingInput) -> ModelRoutingDecision:
        profile_name = self._pick_profile(inp)
        profile = self.models.profiles.get(profile_name)
        if profile is None:
            # Fall back to local_fast if defined, else any local profile
            profile = self.models.profiles.get("local_fast")
            if profile is None:
                raise RuntimeError("no model profiles configured")
            profile_name = "local_fast"

        # Enforce hard privacy rules regardless of selected profile
        if inp.effective_privacy_level in (PrivacyLevel.private_raw, PrivacyLevel.company_sensitive):
            if profile.provider == "cloud":
                # Cannot use cloud; force down to local_fast if available
                local = self.models.profiles.get("local_fast")
                if local is not None:
                    profile = local
                    profile_name = "local_fast"
            allows_external = False
            requires_confirmation = False
        elif inp.effective_privacy_level == PrivacyLevel.private_summary:
            allows_external = profile.provider == "cloud"
            requires_confirmation = allows_external  # cloud escalation needs confirm
        else:  # public
            allows_external = profile.provider == "cloud"
            requires_confirmation = False

        return ModelRoutingDecision(
            task_type=inp.task_type,
            risk_level=inp.risk_level,
            effective_privacy_level=inp.effective_privacy_level,
            selected_profile=profile_name,
            provider=profile.provider,
            model_name=profile.model,
            requires_user_confirmation=requires_confirmation,
            allows_external_model=allows_external,
            reason=self._reason(profile_name, profile, inp),
            suggested_max_tokens=profile.max_tokens,
            suggested_temperature=profile.temperature,
        )

    # ----- internals -----

    def _pick_profile(self, inp: RoutingInput) -> str:
        # Risk override: high risk on private data → local_fast
        if inp.risk_level == "high" and inp.effective_privacy_level in (
            PrivacyLevel.private_raw,
            PrivacyLevel.company_sensitive,
        ):
            return "local_fast"

        # Privacy hard gate: private_raw / company_sensitive → local only
        if inp.effective_privacy_level in (
            PrivacyLevel.private_raw,
            PrivacyLevel.company_sensitive,
        ):
            return "local_fast"

        default = self.models.task_defaults.get(inp.task_type)
        if default and default in self.models.profiles:
            # Cloud default may still apply, but caller will re-check allows_external
            return default

        return "local_fast"

    def _reason(self, profile_name: str, profile: ProfileConfig, inp: RoutingInput) -> str:
        bits = [
            f"profile={profile_name}",
            f"provider={profile.provider}",
            f"task={inp.task_type}",
            f"privacy={inp.effective_privacy_level.value}",
        ]
        if inp.effective_privacy_level in (
            PrivacyLevel.private_raw,
            PrivacyLevel.company_sensitive,
        ):
            bits.append("external_blocked")
        elif inp.effective_privacy_level == PrivacyLevel.private_summary and profile.provider == "cloud":
            bits.append("cloud_escalation_needs_confirmation")
        return " ".join(bits)
