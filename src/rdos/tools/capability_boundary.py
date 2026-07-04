"""CapabilityBoundary — enforce filesystem safety on tool inputs.

Stops path traversal, symlink escape, secret reads, oversized reads.
Independent of any specific tool; tools compose these checks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Default blocked filename patterns. Never readable regardless of allowed_roots.
BLOCKED_NAME_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "id_rsa",
    "id_rsa.pub",
    "id_ed25519",
    "id_ed25519.pub",
    "credentials",
    "credentials.json",
    "secrets.json",
    "secrets.yaml",
    "secrets.yml",
    ".npmrc",
    ".pypirc",
    ".aws/credentials",
    ".ssh/id_rsa",
    ".ssh/id_ed25519",
    ".netrc",
    ".pgpass",
)


@dataclass
class BoundaryResult:
    allowed: bool
    reason: str
    resolved_path: str = ""
    normalized_root: str = ""


class CapabilityBoundary:
    """Enforce path safety for file-reading tools."""

    def __init__(
        self,
        allowed_roots: list[str] | None = None,
        blocked_patterns: list[str] | None = None,
        max_bytes: int = 1 * 1024 * 1024,
    ) -> None:
        self.allowed_roots = [str(Path(r).resolve()) for r in (allowed_roots or [])]
        self.blocked_patterns = tuple(blocked_patterns or BLOCKED_NAME_PATTERNS)
        self.max_bytes = max_bytes

    def check_read(self, raw_path: str) -> BoundaryResult:
        # Reject obvious traversal attempts before resolving.
        if ".." in Path(raw_path).parts:
            return BoundaryResult(
                allowed=False,
                reason="path traversal (..) is not allowed",
            )

        # Resolve to absolute, following symlinks.
        try:
            resolved = Path(raw_path).resolve(strict=False)
        except (OSError, RuntimeError) as exc:
            return BoundaryResult(allowed=False, reason=f"cannot resolve path: {exc}")

        # Must be inside an allowed root.
        chosen_root = ""
        for root in self.allowed_roots:
            try:
                resolved.relative_to(root)
                chosen_root = root
                break
            except ValueError:
                continue
        if not chosen_root:
            return BoundaryResult(
                allowed=False,
                reason=f"path is outside all allowed_roots: {resolved}",
                resolved_path=str(resolved),
            )

        # Block secrets by name (case-insensitive suffix match).
        name = resolved.name.lower()
        full_posix = str(resolved).lower()
        for pat in self.blocked_patterns:
            pat_l = pat.lower()
            if full_posix.endswith(pat_l) or name == pat_l:
                return BoundaryResult(
                    allowed=False,
                    reason=f"blocked secret pattern: {pat}",
                    resolved_path=str(resolved),
                    normalized_root=chosen_root,
                )

        # Reject symlink that escapes allowed_root.
        if resolved.is_symlink():
            try:
                target = Path(os.readlink(resolved)).resolve()
                try:
                    target.relative_to(chosen_root)
                except ValueError:
                    return BoundaryResult(
                        allowed=False,
                        reason=f"symlink escapes allowed_root: target={target}",
                        resolved_path=str(resolved),
                        normalized_root=chosen_root,
                    )
            except OSError as exc:
                return BoundaryResult(
                    allowed=False,
                    reason=f"cannot read symlink target: {exc}",
                    resolved_path=str(resolved),
                    normalized_root=chosen_root,
                )

        # Enforce max_bytes.
        try:
            size = resolved.stat().st_size
        except OSError as exc:
            return BoundaryResult(
                allowed=False,
                reason=f"cannot stat path: {exc}",
                resolved_path=str(resolved),
                normalized_root=chosen_root,
            )
        if size > self.max_bytes:
            return BoundaryResult(
                allowed=False,
                reason=f"file size {size} exceeds max_bytes {self.max_bytes}",
                resolved_path=str(resolved),
                normalized_root=chosen_root,
            )

        return BoundaryResult(
            allowed=True,
            reason="path is within allowed roots and passes safety checks",
            resolved_path=str(resolved),
            normalized_root=chosen_root,
        )
