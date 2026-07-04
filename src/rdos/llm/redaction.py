r"""Redaction — 8 recognizers + configurable replacement strategy.

Used by cloud escalation (private_summary) to scrub chunks before sending
to external model. Last-line-of-defense is `prompt_privacy_validator`.

Recognizers:
  EMAIL         — standard email regex
  PHONE_TW      — 09xxxxxxxx, +886xxxxxxxxx, 02-xxxx-xxxx
  ID_TW         — Taiwan national ID [A-Z]\d{9}
  URL           — http(s)://...
  COMPANY_HINT  — names from configs/redaction.yaml
  IP            — IPv4 + IPv6
  CREDIT_CARD   — 16-digit Luhn-valid
  ADDRESS_TW    — county/city/road/number regex
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Recognition:
    type: str
    start: int
    end: int
    text: str
    replacement: str


# ----- recognizer patterns -----

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_TW_MOBILE_RE = re.compile(r"\b09\d{2}[\-\s]?\d{3}[\-\s]?\d{3}\b")
_PHONE_TW_LANDLINE_RE = re.compile(r"\+?886[\-\s]?[2-9]\d{1,2}[\-\s]?\d{3,4}[\-\s]?\d{3,4}\b")
_PHONE_TW_AREA_RE = re.compile(r"\b0[2-8][\-\s]?\d{3,4}[\-\s]?\d{3,4}\b")
_ID_TW_RE = re.compile(r"\b[A-Z][1-2]\d{8}\b")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_IPv4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPv6_RE = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b")
_CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
_ADDRESS_TW_RE = re.compile(
    r"(?:台北市|新北市|桃園市|台中市|台南市|高雄市|基隆市|新竹市|嘉義市|"
    r"台北縣|桃園縣|新竹縣|苗栗縣|彰化縣|南投縣|雲林縣|嘉義縣|屏東縣|宜蘭縣|花蓮縣|台東縣|澎湖縣|"
    r"[^。\s]{0,8}?[路街大道][^。\s]{0,12}?\d+號)"
)


def _luhn_valid(digits: str) -> bool:
    s = 0
    parity = False
    for ch in reversed(digits):
        if not ch.isdigit():
            return False
        n = int(ch)
        if parity:
            n *= 2
            if n > 9:
                n -= 9
        s += n
        parity = not parity
    return s % 10 == 0


def _replace_format(type_: str, *, strategy: str, fmt: str, payload: str) -> str:
    if strategy == "mask":
        if type_ == "EMAIL" and "@" in payload:
            u, d = payload.split("@", 1)
            return f"{u[0]}***@{d[0]}***.***"
        if len(payload) > 4:
            return payload[:2] + "*" * (len(payload) - 4) + payload[-2:]
        return "***"
    if strategy == "hash":
        import hashlib

        return f"[REDACTED-{hashlib.sha256(payload.encode()).hexdigest()[:8]}]"
    # default placeholder
    return fmt.replace("{TYPE}", type_)


def _recognize_email(text: str, strategy: str, fmt: str) -> list[Recognition]:
    return [
        Recognition(
            type="EMAIL",
            start=m.start(),
            end=m.end(),
            text=m.group(0),
            replacement=_replace_format("EMAIL", strategy=strategy, fmt=fmt, payload=m.group(0)),
        )
        for m in _EMAIL_RE.finditer(text)
    ]


def _recognize_phone_tw(text: str, strategy: str, fmt: str) -> list[Recognition]:
    out: list[Recognition] = []
    for pat, name in (
        (_PHONE_TW_MOBILE_RE, "PHONE-TW-MOBILE"),
        (_PHONE_TW_LANDLINE_RE, "PHONE-TW-LAND"),
        (_PHONE_TW_AREA_RE, "PHONE-TW-AREA"),
    ):
        for m in pat.finditer(text):
            out.append(
                Recognition(
                    type=name,
                    start=m.start(),
                    end=m.end(),
                    text=m.group(0),
                    replacement=_replace_format("PHONE-TW", strategy=strategy, fmt=fmt, payload=m.group(0)),
                )
            )
    return out


def _recognize_id_tw(text: str, strategy: str, fmt: str) -> list[Recognition]:
    return [
        Recognition(
            type="ID-TW",
            start=m.start(),
            end=m.end(),
            text=m.group(0),
            replacement=_replace_format("ID-TW", strategy=strategy, fmt=fmt, payload=m.group(0)),
        )
        for m in _ID_TW_RE.finditer(text)
    ]


def _recognize_url(text: str, strategy: str, fmt: str) -> list[Recognition]:
    return [
        Recognition(
            type="URL",
            start=m.start(),
            end=m.end(),
            text=m.group(0),
            replacement=_replace_format("URL", strategy=strategy, fmt=fmt, payload=m.group(0)),
        )
        for m in _URL_RE.finditer(text)
    ]


def _recognize_ip(text: str, strategy: str, fmt: str) -> list[Recognition]:
    out: list[Recognition] = []
    for m in _IPv4_RE.finditer(text):
        parts = m.group(0).split(".")
        if all(0 <= int(p) <= 255 for p in parts):
            out.append(
                Recognition(
                    type="IP",
                    start=m.start(),
                    end=m.end(),
                    text=m.group(0),
                    replacement=_replace_format("IP", strategy=strategy, fmt=fmt, payload=m.group(0)),
                )
            )
    for m in _IPv6_RE.finditer(text):
        out.append(
            Recognition(
                type="IP",
                start=m.start(),
                end=m.end(),
                text=m.group(0),
                replacement=_replace_format("IP", strategy=strategy, fmt=fmt, payload=m.group(0)),
            )
        )
    return out


def _recognize_credit_card(text: str, strategy: str, fmt: str) -> list[Recognition]:
    out: list[Recognition] = []
    for m in _CREDIT_CARD_RE.finditer(text):
        digits = re.sub(r"[^\d]", "", m.group(0))
        if 13 <= len(digits) <= 16 and _luhn_valid(digits):
            out.append(
                Recognition(
                    type="CREDIT-CARD",
                    start=m.start(),
                    end=m.end(),
                    text=m.group(0),
                    replacement=_replace_format("CREDIT-CARD", strategy=strategy, fmt=fmt, payload=m.group(0)),
                )
            )
    return out


def _recognize_address_tw(text: str, strategy: str, fmt: str) -> list[Recognition]:
    return [
        Recognition(
            type="ADDRESS-TW",
            start=m.start(),
            end=m.end(),
            text=m.group(0),
            replacement=_replace_format("ADDRESS-TW", strategy=strategy, fmt=fmt, payload=m.group(0)),
        )
        for m in _ADDRESS_TW_RE.finditer(text)
    ]


def _recognize_company(text: str, names: list[str], strategy: str, fmt: str) -> list[Recognition]:
    out: list[Recognition] = []
    for name in names:
        if not name:
            continue
        for m in re.finditer(re.escape(name), text):
            out.append(
                Recognition(
                    type="COMPANY-HINT",
                    start=m.start(),
                    end=m.end(),
                    text=m.group(0),
                    replacement=_replace_format("COMPANY", strategy=strategy, fmt=fmt, payload=m.group(0)),
                )
            )
    return out


# ----- public API -----


RECOGNIZER_FUNCS: dict[str, Any] = {
    "EMAIL": lambda text, cfg: _recognize_email(text, cfg["replacement_strategy"], cfg["placeholder_format"]),
    "PHONE_TW": lambda text, cfg: _recognize_phone_tw(text, cfg["replacement_strategy"], cfg["placeholder_format"]),
    "ID_TW": lambda text, cfg: _recognize_id_tw(text, cfg["replacement_strategy"], cfg["placeholder_format"]),
    "URL": lambda text, cfg: _recognize_url(text, cfg["replacement_strategy"], cfg["placeholder_format"]),
    "IP": lambda text, cfg: _recognize_ip(text, cfg["replacement_strategy"], cfg["placeholder_format"]),
    "CREDIT_CARD": lambda text, cfg: _recognize_credit_card(text, cfg["replacement_strategy"], cfg["placeholder_format"]),
    "ADDRESS_TW": lambda text, cfg: _recognize_address_tw(text, cfg["replacement_strategy"], cfg["placeholder_format"]),
    "COMPANY_HINT": lambda text, cfg: _recognize_company(text, cfg.get("company_names", []), cfg["replacement_strategy"], cfg["placeholder_format"]),
}


def load_redaction_config(path: str | Path = "configs/redaction.yaml") -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "enabled_recognizers": list(RECOGNIZER_FUNCS.keys()),
            "company_names": [],
            "replacement_strategy": "placeholder",
            "placeholder_format": "[REDACTED-{TYPE}]",
        }
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {
        "enabled_recognizers": raw.get("enabled_recognizers", list(RECOGNIZER_FUNCS.keys())),
        "company_names": raw.get("company_names", []),
        "replacement_strategy": raw.get("replacement_strategy", "placeholder"),
        "placeholder_format": raw.get("placeholder_format", "[REDACTED-{TYPE}]"),
    }


def scan(text: str, cfg: dict[str, Any] | None = None) -> list[Recognition]:
    """Run all enabled recognizers on `text`. Returns recognitions sorted by start."""
    cfg = cfg or load_redaction_config()
    out: list[Recognition] = []
    for name in cfg["enabled_recognizers"]:
        fn = RECOGNIZER_FUNCS.get(name)
        if fn is None:
            continue
        out.extend(fn(text, cfg))
    # Sort by start, then drop overlaps (keep the longest).
    out.sort(key=lambda r: (r.start, -(r.end - r.start)))
    return _drop_overlaps(out)


def redact(text: str, cfg: dict[str, Any] | None = None) -> tuple[str, list[Recognition]]:
    """Apply recognizers and return (redacted_text, recognitions)."""
    cfg = cfg or load_redaction_config()
    recs = scan(text, cfg)
    if not recs:
        return text, []
    parts: list[str] = []
    cursor = 0
    for r in recs:
        parts.append(text[cursor : r.start])
        parts.append(r.replacement)
        cursor = r.end
    parts.append(text[cursor:])
    return "".join(parts), recs


def _drop_overlaps(recs: list[Recognition]) -> list[Recognition]:
    out: list[Recognition] = []
    last_end = -1
    for r in recs:
        if r.start >= last_end:
            out.append(r)
            last_end = r.end
    return out
