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
TIME_SPAN_FIELDS = frozenset(
    {FieldName.DURATION.value, FieldName.BID_VALIDITY.value}
)
COMPACT_TEXT_FIELDS = frozenset(
    {
        FieldName.PROJECT_NAME.value,
        FieldName.PROJECT_NUMBER.value,
        FieldName.TENDER_NUMBER.value,
        FieldName.PURCHASER.value,
        FieldName.TENDER_AGENCY.value,
        FieldName.PROJECT_LOCATION.value,
        FieldName.PROCUREMENT_SCOPE.value,
        FieldName.QUALITY_TARGET.value,
        FieldName.BID_OPEN_LOCATION.value,
        FieldName.ELECTRONIC_PLATFORM.value,
    }
)
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


_CHINESE_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "壹": 1,
    "二": 2,
    "贰": 2,
    "两": 2,
    "三": 3,
    "叁": 3,
    "四": 4,
    "肆": 4,
    "五": 5,
    "伍": 5,
    "六": 6,
    "陆": 6,
    "七": 7,
    "柒": 7,
    "八": 8,
    "捌": 8,
    "九": 9,
    "玖": 9,
}
_CHINESE_SMALL_UNITS = {"十": 10, "拾": 10, "百": 100, "佰": 100, "千": 1000, "仟": 1000}
_CHINESE_LARGE_UNITS = {"万": 10_000, "亿": 100_000_000}


def _parse_chinese_integer(value: str) -> int | None:
    total = 0
    section = 0
    number = 0
    seen = False
    for char in value:
        if char in _CHINESE_DIGITS:
            number = _CHINESE_DIGITS[char]
            seen = True
        elif char in _CHINESE_SMALL_UNITS:
            unit = _CHINESE_SMALL_UNITS[char]
            if number == 0:
                number = 1
            section += number * unit
            number = 0
            seen = True
        elif char in _CHINESE_LARGE_UNITS:
            unit = _CHINESE_LARGE_UNITS[char]
            section += number
            if section == 0:
                section = 1
            total += section * unit
            section = 0
            number = 0
            seen = True
        else:
            return None
    return total + section + number if seen else None


def normalize_money(value: object) -> str | None:
    """Extract exactly one reliable numeric money value from a candidate.

    Tender documents commonly append tax or item-limit notes after the amount,
    so a full-string match is too strict.  Conversely, a sentence containing
    no numeric money token is never allowed to become a resolved amount.
    """

    text = normalize_text_value(value).replace("人民币", "")
    matches = list(
        re.finditer(
            r"(?<![\d.])(?:[¥￥]\s*)?(?P<number>\d[\d,]*(?:\.\d+)?)"
            r"\s*(?P<unit>万元|万|元)",
            text,
        )
    )
    if len(matches) != 1:
        chinese_matches = list(
            re.finditer(
                r"(?P<number>[零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟]+)"
                r"\s*(?P<unit>万元|万|元)",
                text,
            )
        )
        if len(chinese_matches) != 1:
            return None
        chinese = chinese_matches[0]
        parsed = _parse_chinese_integer(chinese.group("number"))
        if parsed is None:
            return None
        amount = Decimal(parsed)
        if chinese.group("unit") in {"万元", "万"}:
            amount *= Decimal("10000")
        return _decimal_to_string(amount)

    match = matches[0]
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
    # Preserve reference phrases as invalid typed values.  They remain in the
    # candidate list for review but can never be normalized into a datetime.
    compact = re.sub(r"\s+", "", text)
    compact = re.sub(r"[（(](?:北京时间|当地时间|以公告为准)[）)]$", "", compact)
    compact = compact.rstrip("。；;，,")
    if re.search(
        r"^(?:同(?:投标|提交响应文件|响应文件递交|响应文件提交).{0,8}截止(?:时间)?|"
        r"详见投标人须知|按招标文件要求|见投标人须知)",
        compact,
    ):
        return None
    text = compact
    text = text.replace("时", ":").replace("分", "").replace("秒", "")
    # Numeric dates may use a separating space before the clock; keep that
    # separator for the second pattern while accepting Chinese no-space form.
    numeric_text = re.sub(r"\s+", " ", normalize_text_value(value)).replace("：", ":")
    patterns = (
        re.compile(
            r"(?P<year>\d{4})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日"
            r"(?:(?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
            r"(?::(?P<second>\d{1,2}))?)?"
        ),
        re.compile(
            r"(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})"
            r"(?:[T ](?P<hour>\d{1,2}):(?P<minute>\d{1,2})"
            r"(?::(?P<second>\d{1,2}))?)?"
        ),
    )
    for pattern_index, pattern in enumerate(patterns):
        match = pattern.fullmatch(text if pattern_index == 0 else numeric_text)
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
    match = re.search(
        r"(?P<number>\d+(?:\.\d+)?)\s*个?\s*(?P<unit>日历天|天|个月|月|年)",
        text,
    )
    if not match:
        return None
    number = match.group("number")
    if number.endswith(".0"):
        number = number[:-2]
    unit = match.group("unit")
    if unit == "天":
        unit = "日历天"
    if unit in {"月", "个月"}:
        unit = "个月"
    return f"{number}{unit}"


def normalize_boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
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
        return normalized
    elif field in DATE_FIELDS:
        normalized = normalize_date_time(value)
        return normalized
    elif field in TIME_SPAN_FIELDS:
        normalized = normalize_duration(value)
        return normalized
    elif field == FieldName.CONSORTIUM_ALLOWED.value:
        normalized = normalize_boolean(value)
        return normalized

    normalized_text = normalize_text_value(value)
    if field in COMPACT_TEXT_FIELDS:
        normalized_text = re.sub(r"\s+", "", normalized_text)
    return normalized_text


def is_value_type_valid(field: str | FieldName, value: object) -> bool:
    """Return whether a candidate can legally participate in resolution."""

    field_name = field.value if isinstance(field, FieldName) else str(field)
    if value is None or not normalize_text_value(value):
        return False
    if field_name in MONEY_FIELDS | DATE_FIELDS | TIME_SPAN_FIELDS:
        return normalize_field_value(field_name, value) is not None
    if field_name == FieldName.CONSORTIUM_ALLOWED.value:
        return normalize_boolean(value) is not None
    return True


def is_resolved_value_type_valid(field: str | FieldName, value: object) -> bool:
    """Validate the canonical value stored on a resolved ProjectFacts field."""

    field_name = field.value if isinstance(field, FieldName) else str(field)
    if value is None or not normalize_text_value(value):
        return False
    if field_name in MONEY_FIELDS:
        text = normalize_text_value(value)
        return bool(re.fullmatch(r"\d+(?:\.\d+)?", text)) or normalize_money(text) is not None
    if field_name == FieldName.CONSORTIUM_ALLOWED.value:
        return isinstance(value, bool)
    return is_value_type_valid(field_name, value)


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
    "COMPACT_TEXT_FIELDS",
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
    "is_value_type_valid",
    "is_resolved_value_type_valid",
]
