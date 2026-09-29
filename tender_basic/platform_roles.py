"""Platform-role resolution.

One procurement project legitimately names several platforms, each with its own
role::

    河南国企阳光招采服务平台          -> the procurement service platform (register,
                                        download the document, upload the response)
    e招投标交易平台                    -> the transaction system inside it
    中国招标投标公共服务平台            -> the statutory announcement platform
    远程开标大厅                       -> the opening / decryption venue

Collapsing them into one "electronic platform" fact makes the candidates look
contradictory ("Conflicting candidate values remain after normalization.") and
hides the role each name plays.  This module classifies a platform mention by
role so the fact can resolve to the platform that actually governs electronic
submission, while the other roles stay visible as roles rather than conflicts.
"""

from __future__ import annotations

import re
from typing import Iterable, Mapping

ROLE_PROCUREMENT_SERVICE = "PROCUREMENT_SERVICE_PLATFORM"
ROLE_TRANSACTION = "TRANSACTION_SYSTEM"
ROLE_UPLOAD = "UPLOAD_PLATFORM"
ROLE_OPENING = "OPENING_PLATFORM"
ROLE_ANNOUNCEMENT = "ANNOUNCEMENT_PLATFORM"
ROLE_UNKNOWN = ""

PLATFORM_ROLES: tuple[str, ...] = (
    ROLE_PROCUREMENT_SERVICE,
    ROLE_TRANSACTION,
    ROLE_UPLOAD,
    ROLE_OPENING,
    ROLE_ANNOUNCEMENT,
)

ROLE_LABELS: dict[str, str] = {
    ROLE_PROCUREMENT_SERVICE: "采购服务平台",
    ROLE_TRANSACTION: "交易系统",
    ROLE_UPLOAD: "上传平台",
    ROLE_OPENING: "开标平台",
    ROLE_ANNOUNCEMENT: "公告发布平台",
}

#: how strongly each role governs the *electronic submission* of a response
ROLE_PRIORITY: dict[str, int] = {
    ROLE_PROCUREMENT_SERVICE: 0,
    ROLE_UPLOAD: 1,
    ROLE_TRANSACTION: 2,
    ROLE_OPENING: 3,
    ROLE_ANNOUNCEMENT: 4,
}

#: name-level cues, most specific first
_NAME_CUES: tuple[tuple[str, str], ...] = (
    (ROLE_ANNOUNCEMENT, r"(公共服务平台|公告发布|招标投标公共服务)"),
    (ROLE_OPENING, r"(开标大厅|远程开标|不见面开标|在线解密)"),
    (ROLE_TRANSACTION, r"(交易平台|交易系统|招投标交易|e招投标)"),
    (ROLE_PROCUREMENT_SERVICE, r"(招采服务平台|阳光招采|采购服务平台|电子采购平台|公共资源交易中心)"),
)
#: context cues (the sentence the platform name came from)
_CONTEXT_CUES: tuple[tuple[str, str], ...] = (
    (ROLE_OPENING, r"(开标|解密|唱标|签到)"),
    (ROLE_UPLOAD, r"(上传|递交|提交响应文件|加密上传)"),
    (ROLE_ANNOUNCEMENT, r"(公告发布|发布公告|公告媒介|公示)"),
    (ROLE_PROCUREMENT_SERVICE, r"(获取|下载|购买).{0,8}(询比文件|招标文件|采购文件)"),
    (ROLE_TRANSACTION, r"(交易|投标活动)"),
)


def classify_platform_role(value: str, *, context: str = "") -> str:
    """The role a platform name (optionally with its sentence) plays."""

    name = re.sub(r"[\s\u3000]+", "", str(value or ""))
    if not name:
        return ROLE_UNKNOWN
    for role, pattern in _NAME_CUES:
        if re.search(pattern, name):
            return role
    surroundings = re.sub(r"[\s\u3000]+", "", str(context or ""))
    if surroundings:
        for role, pattern in _CONTEXT_CUES:
            if re.search(pattern, surroundings):
                return role
    return ROLE_UNKNOWN


def resolve_platform_roles(
    entries: Iterable[tuple[str, str]],
) -> tuple[str, dict[str, str], dict[str, str]]:
    """``(resolved_value, role -> value, value -> role)`` for the platform field.

    The resolved value is the platform that governs electronic submission
    (procurement service platform first, then the upload/transaction system); the
    announcement platform is never chosen for that field because it publishes the
    notice and does not receive responses.
    """

    by_role: dict[str, str] = {}
    value_roles: dict[str, str] = {}
    for value, context in entries:
        text = str(value or "").strip()
        if not text:
            continue
        role = classify_platform_role(text, context=context)
        value_roles[text] = role
        if role and role not in by_role:
            by_role[role] = text
    candidates = [
        (ROLE_PRIORITY.get(role, 9), -len(value), value)
        for role, value in by_role.items()
        if role != ROLE_ANNOUNCEMENT
    ]
    candidates.sort()
    resolved = candidates[0][2] if candidates else ""
    return resolved, by_role, value_roles


def role_breakdown_text(by_role: Mapping[str, str]) -> str:
    """A reviewer-facing sentence naming each platform and its role."""

    parts = [
        f"{ROLE_LABELS.get(role, role)}：{by_role[role]}"
        for role in PLATFORM_ROLES
        if role in by_role
    ]
    return "；".join(parts)


__all__ = [
    "PLATFORM_ROLES",
    "ROLE_LABELS",
    "ROLE_PRIORITY",
    "ROLE_PROCUREMENT_SERVICE",
    "ROLE_TRANSACTION",
    "ROLE_UPLOAD",
    "ROLE_OPENING",
    "ROLE_ANNOUNCEMENT",
    "ROLE_UNKNOWN",
    "classify_platform_role",
    "resolve_platform_roles",
    "role_breakdown_text",
]
