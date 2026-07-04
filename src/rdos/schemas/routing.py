"""Model routing schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from rdos.schemas.privacy import PrivacyLevel


class ModelRoutingDecision(BaseModel):
    """Output of ModelRouter.

    Carries enough context that the orchestrator can pick the right
    adapter and know whether to prompt the user for confirmation.

    NOTE: ModelRouter must NOT return a pre-bound model with tools.
    Only metadata about which profile to use.
    """

    task_type: str
    risk_level: str = "low"
    effective_privacy_level: PrivacyLevel
    selected_profile: str
    provider: str
    model_name: str
    requires_user_confirmation: bool = False
    allows_external_model: bool
    reason: str = ""

    # Hints passed to the adapter; never a callable model.
    suggested_max_tokens: int | None = None
    suggested_temperature: float | None = None
    suggested_response_format: dict[str, str] | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
