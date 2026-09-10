"""Small deterministic normalizers used before ProjectFacts resolution."""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Mapping

from .models import CandidateFact, FieldName


MONEY_FIELDS = frozenset(
    {FieldName.BUDGET.value, FieldName.MAX_PRICE.value, FieldName.BID_BOND_AMOUNT.value}
)
DATE_FIELDS = frozenset({FieldName.BID_DEADLINE.value, FieldName.BID_OPEN_TIME.value})
IDENTIFIER_FIELDS = frozenset(
    {
        FieldName.PROJECT_NUMBER.value,
        FieldName.TENDER_NUMBER.value,
        FieldName.LOT_NUMBER.value,
    }
)


def normalize_text_value(value: object) -> str:
    """Normalize whitespace/full-width forms without deleting meaningful punctuation."""

    text = unicodedata.normalize("NFKC", str(value))
    text = "".join(" " if char.isspace() else char for char in text)
    return re.sub(r" +", " ", text).strip()


def _decimal_to_string(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def normalize_money(value: object) -> str | None:
    text = normalize_text_value(value).replace("人民币", "")
    match = re.fullmatch(
        r"[¥￥]?\s*(?P<number>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>万元|万|元)?",
        text,
    )
    if not match:
        return None

    try:
        amount = Decimal(match.group("number").replace(",", ""))
    except InvalidOperation:
        return None
    if match.group("unit") in {"万元", "万"}:
        amount *= Decimal("10000")
    return _decimal_to_string(amount)


def _valid_datetime(
    year: int,
    month: int,
    day: int,
    hour: int | None = None,
    minute: int | None = None,
    second: int | None = None,
) -> str | None:
    try:
        value = datetime(
            year,
            month,
            day,
            hour or 0,
            minute or 0,
            second or 0,
        )
    except ValueError:
        return None

    result = value.strftime("%Y-%m-%d")
    if hour is not None and minute is not None:
        result += f" {hour:02d}:{minute:02d}"
        if second is not None:
            result += f":{second:02d}"
    return result


def normalize_date_time(value: object) -> str | None:
    text = normalize_text_value(value).replace("：", ":")
    patterns = (
        re.compile(
            r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日"
            r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
            r"(?::(?P<second>\d{1,2}))?)?"
        ),
        re.compile(
            r"(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})"
            r"(?:\s+(?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
            r"(?::(?P<second>\d{1,2}))?)?"
        ),
    )
    for pattern in patterns:
        match = pattern.fullmatch(text)
        if not match:
            continue
        groups = match.groupdict()
        return _valid_datetime(
            int(groups["year"]),
            int(groups["month"]),
            int(groups["day"]),
            int(groups["hour"]) if groups["hour"] else None,
            int(groups["minute"]) if groups["minute"] else None,
            int(groups["second"]) if groups["second"] else None,
        )
    return None


def normalize_duration(value: object) -> str | None:
    text = normalize_text_value(value)
    match = re.fullmatch(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>日历天|天|个月|月)", text)
    if not match:
        return None
    number = match.group("number")
    if number.endswith(".0"):
        number = number[:-2]
    return f"{number}{match.group('unit')}"


def normalize_boolean(value: object) -> bool | None:
    text = normalize_text_value(value)
    false_phrases = (
        "不接受",
        "不允许",
        "不得",
        "禁止",
        "不是",
        "不可以",
        "不可",
        "否",
    )
    true_phrases = ("接受", "允许", "可以", "是")

    if any(phrase in text for phrase in false_phrases):
        return False
    if any(phrase in text for phrase in true_phrases):
        return True
    return None


def normalize_field_value(field: str, value: object) -> str | bool | None:
    """Return a comparison value while leaving CandidateFact.value untouched."""

    if value is None:
        return None
    if field in MONEY_FIELDS:
        normalized = normalize_money(value)
        if normalized is not None:
            return normalized
    elif field in DATE_FIELDS:
        normalized = normalize_date_time(value)
        if normalized is not None:
            return normalized
    elif field == FieldName.DURATION.value:
        normalized = normalize_duration(value)
        if normalized is not None:
            return normalized
    elif field == FieldName.CONSORTIUM_ALLOWED.value:
        normalized = normalize_boolean(value)
        if normalized is not None:
            return normalized

    return normalize_text_value(value)


def _locator_key(candidate: CandidateFact) -> str:
    return json.dumps(
        candidate.locator.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )


def normalize_candidates(
    candidates_by_field: Mapping[str, list[CandidateFact]],
) -> dict[str, list[CandidateFact]]:
    """Normalize and deterministically de-duplicate candidates per field."""

    normalized_by_field: dict[str, list[CandidateFact]] = {}
    for field in FieldName:
        normalized: list[CandidateFact] = []
        seen: set[tuple[str, str, str]] = set()
        for candidate in candidates_by_field.get(field.value, []):
            normalized_value = normalize_field_value(field.value, candidate.value)
            normalized_candidate = candidate.model_copy(
                update={"normalized_value": normalized_value}
            )
            key = (
                normalized_candidate.method,
                _locator_key(normalized_candidate),
                json.dumps(normalized_value, ensure_ascii=False, sort_keys=True),
            )
            if key in seen:
                continue
            seen.add(key)
            normalized.append(normalized_candidate)
        normalized_by_field[field.value] = normalized
    return normalized_by_field


__all__ = [
    "DATE_FIELDS",
    "IDENTIFIER_FIELDS",
    "MONEY_FIELDS",
    "normalize_boolean",
    "normalize_candidates",
    "normalize_date_time",
    "normalize_duration",
    "normalize_field_value",
    "normalize_money",
    "normalize_text_value",
]
