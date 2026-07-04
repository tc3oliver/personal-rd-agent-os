"""Export tool — produces approval_required decision, never writes silently."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ExportRequest:
    target_path: str
    content: str
    format: str = "markdown"


class ExportReportTool:
    name = "export_report"
    description = (
        "Export a synthesized report to disk. Requires approval per policy "
        "(set requires_approval=true in tool_policy.yaml for the relevant privacy level)."
    )

    def __init__(self, *, default_out_dir: str = "data/generated/reports") -> None:
        self.default_out_dir = default_out_dir

    def build_request(self, *, target_path: str, content: str, **_kwargs: Any) -> ExportRequest:
        return ExportRequest(target_path=target_path, content=content)

    def run(self, *, target_path: str, content: str, **_kwargs: Any) -> dict[str, Any]:
        """ToolRegistry blocks this when requires_approval is set; only invoked if approved."""
        from pathlib import Path

        p = Path(target_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {
            "path": str(p.resolve()),
            "bytes": len(content),
            "format": _kwargs.get("format", "markdown"),
        }
