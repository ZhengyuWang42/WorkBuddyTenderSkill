"""Semantic role taxonomy for review numbers (round 5).

Round 4 proved that *rendering* is provenance-consistent; the CASE001 human
review then showed that a number can be traceable and still be assigned the
wrong business meaning ("质保金比例为 95%").  Round 5 therefore separates the
roles the workbook may use and forbids the generic buckets

    PERCENTAGE / PRICE / MONTHS / QUANTITY / OTHER

whenever the business meaning is known.

This module is deliberately free of project imports: it is the leaf vocabulary
shared by :mod:`tender_basic.review_point` (which classifies numbers) and
:mod:`tender_basic.concern_contract` (which validates that a concern only uses
the roles its contract allows).
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# canonical roles
# --------------------------------------------------------------------------- #

#: money that belongs to the *response* bond (响应保证金/投标保证金)
ROLE_RESPONSE_BOND = "RESPONSE_BOND"
#: money that belongs to the *performance* bond (履约保证金)
ROLE_PERFORMANCE_BOND = "PERFORMANCE_BOND"
#: bond money whose business meaning the source does not state
ROLE_BOND_AMOUNT = "BOND_AMOUNT"
#: the accepted form of a bond (银行转账/银行保函/保险), not an amount
ROLE_BOND_FORM = "BOND_FORM"

#: 最高限价/控制价/预算 as a ceiling the bidder must not exceed
ROLE_PRICE_CEILING = "PRICE_CEILING"
#: a quotation that carries no finer business meaning
ROLE_PRICE = "PRICE"

#: ratio of the contract price paid under a payment condition (95%)
ROLE_PAYMENT_RATIO = "PAYMENT_RATIO"
#: money kept back as retention/guarantee money (5%)
ROLE_RETENTION_MONEY_RATIO = "RETENTION_MONEY_RATIO"
#: ratio of the price the bidder accepts to be settled by bank acceptance (100%)
ROLE_BANK_ACCEPTANCE_RATIO = "BANK_ACCEPTANCE_RATIO"

#: months of project/product warranty (24 个月)
ROLE_PROJECT_WARRANTY_MONTHS = "PROJECT_WARRANTY_MONTHS"
#: months after which the retention money is released (12 个月)
ROLE_RETENTION_RELEASE_MONTHS = "RETENTION_RELEASE_MONTHS"
#: a delivery/service period (工期/供货期)
ROLE_DELIVERY_DAYS = "DELIVERY_DAYS"
#: a bid/response validity period (有效期)
ROLE_BID_VALIDITY_DAYS = "BID_VALIDITY_DAYS"
#: a service/repair response period (响应时间)
ROLE_RESPONSE_DAYS = "RESPONSE_DAYS"

#: points awarded by a scoring factor (12 分 / 8 分 / 40 分)
ROLE_SCORE_POINTS = "SCORE_POINTS"
#: quantity of goods/services
ROLE_QUANTITY = "QUANTITY"
#: number of people
ROLE_PERSON_COUNT = "PERSON_COUNT"
#: a contact phone number / account / reference, never a requirement value
ROLE_CONTACT_INFO = "CONTACT_INFO"
#: the price of the tender documents (标书费/文件费) -- a purchaser cost
ROLE_TENDER_DOCUMENT_PRICE = "TENDER_DOCUMENT_PRICE"
#: the agency service fee (代理服务费)
ROLE_AGENCY_SERVICE_FEE = "AGENCY_SERVICE_FEE"
#: anything else; never a bidder review value
ROLE_OTHER = "OTHER"

# --------------------------------------------------------------------------- #
# legacy constant names (kept so callers keep importing the same symbols)
# --------------------------------------------------------------------------- #

ROLE_VALIDITY_DAYS = ROLE_BID_VALIDITY_DAYS
ROLE_DURATION_DAYS = ROLE_DELIVERY_DAYS
ROLE_WARRANTY_MONTHS = ROLE_PROJECT_WARRANTY_MONTHS
ROLE_SCORE = ROLE_SCORE_POINTS
ROLE_RETENTION_RELEASE_PERIOD = ROLE_RETENTION_RELEASE_MONTHS
ROLE_CONTACT = ROLE_CONTACT_INFO
ROLE_TENDER_FEE = ROLE_TENDER_DOCUMENT_PRICE
ROLE_BOND = ROLE_BOND_AMOUNT

#: Legacy role names used by the round-2/3/4 registries, mapped onto the round-5
#: taxonomy.  ``canonical_role`` is the single translation point, so a caller can
#: keep its historical vocabulary while the emitted role is always canonical.
LEGACY_ROLE_NAMES: dict[str, str] = {
    "VALIDITY_DAYS": ROLE_BID_VALIDITY_DAYS,
    "DURATION_DAYS": ROLE_DELIVERY_DAYS,
    "WARRANTY_MONTHS": ROLE_PROJECT_WARRANTY_MONTHS,
    "RETENTION_RELEASE_PERIOD": ROLE_RETENTION_RELEASE_MONTHS,
    "SCORE": ROLE_SCORE_POINTS,
    "TENDER_FEE": ROLE_TENDER_DOCUMENT_PRICE,
    "CONTACT": ROLE_CONTACT_INFO,
    "PERCENTAGE": ROLE_OTHER,
    "MONTHS": ROLE_OTHER,
    #: a bare BOND never says *which* bond; the amount role is the neutral one
    "BOND": ROLE_BOND_AMOUNT,
}


def canonical_role(name: str) -> str:
    """Return the round-5 canonical name of a (possibly legacy) role."""

    return LEGACY_ROLE_NAMES.get(name, name)


def is_canonical_role(name: str) -> bool:
    """True when ``name`` is a role of the round-5 taxonomy."""

    return name in ROLE_FAMILY

# --------------------------------------------------------------------------- #
# families
# --------------------------------------------------------------------------- #

FAMILY_RATIO = "RATIO"
FAMILY_MONEY = "MONEY"
FAMILY_DAYS = "DAYS"
FAMILY_MONTHS = "MONTHS"
FAMILY_COUNT = "COUNT"
FAMILY_POINTS = "POINTS"
FAMILY_FORM = "FORM"
FAMILY_TEXT = "TEXT"

ROLE_FAMILY: dict[str, str] = {
    ROLE_RESPONSE_BOND: FAMILY_MONEY,
    ROLE_PERFORMANCE_BOND: FAMILY_MONEY,
    ROLE_BOND_AMOUNT: FAMILY_MONEY,
    ROLE_BOND_FORM: FAMILY_FORM,
    ROLE_PRICE_CEILING: FAMILY_MONEY,
    ROLE_PRICE: FAMILY_MONEY,
    ROLE_PAYMENT_RATIO: FAMILY_RATIO,
    ROLE_RETENTION_MONEY_RATIO: FAMILY_RATIO,
    ROLE_BANK_ACCEPTANCE_RATIO: FAMILY_RATIO,
    ROLE_PROJECT_WARRANTY_MONTHS: FAMILY_MONTHS,
    ROLE_RETENTION_RELEASE_MONTHS: FAMILY_MONTHS,
    ROLE_DELIVERY_DAYS: FAMILY_DAYS,
    ROLE_BID_VALIDITY_DAYS: FAMILY_DAYS,
    ROLE_RESPONSE_DAYS: FAMILY_DAYS,
    ROLE_SCORE_POINTS: FAMILY_POINTS,
    ROLE_QUANTITY: FAMILY_COUNT,
    ROLE_PERSON_COUNT: FAMILY_COUNT,
    ROLE_CONTACT_INFO: FAMILY_TEXT,
    ROLE_TENDER_DOCUMENT_PRICE: FAMILY_MONEY,
    ROLE_AGENCY_SERVICE_FEE: FAMILY_MONEY,
    ROLE_OTHER: FAMILY_TEXT,
}

#: The generic buckets round 5 replaces.  A number whose business meaning is
#: known must never be filed under one of these names; the taxonomy exists so
#: that "5%" of a retention clause and "95%" of a payment condition can never be
#: compared, merged or re-rendered as one another.
GENERIC_BUCKETS: frozenset[str] = frozenset({"PERCENTAGE", "MONTHS", "QUANTITY", "PRICE", "OTHER"})

#: Roles that may never be rendered as a bidder review value at all.
NON_REVIEW_ROLES: frozenset[str] = frozenset(
    {ROLE_CONTACT_INFO, ROLE_TENDER_DOCUMENT_PRICE, ROLE_OTHER}
)

#: The five roles the human brief requires to stay distinct.
DISTINCT_MONEY_ROLES: tuple[str, ...] = (
    ROLE_PROJECT_WARRANTY_MONTHS,
    ROLE_RETENTION_RELEASE_MONTHS,
    ROLE_RETENTION_MONEY_RATIO,
    ROLE_PAYMENT_RATIO,
    ROLE_BANK_ACCEPTANCE_RATIO,
)

#: Which roles may appear inside a row of a given requirement type.  Round 5
#: keeps the type guard but with the finer vocabulary.
ROLES_BY_TYPE: dict[str, frozenset[str]] = {
    "PRICING": frozenset(
        {
            ROLE_PRICE,
            ROLE_PRICE_CEILING,
            ROLE_PAYMENT_RATIO,
            ROLE_RETENTION_MONEY_RATIO,
            ROLE_QUANTITY,
            ROLE_AGENCY_SERVICE_FEE,
        }
    ),
    "BOND": frozenset(
        {ROLE_BOND_AMOUNT, ROLE_RESPONSE_BOND, ROLE_PERFORMANCE_BOND, ROLE_PRICE, ROLE_BOND_FORM}
    ),
    "VALIDITY": frozenset({ROLE_BID_VALIDITY_DAYS}),
    "DURATION": frozenset({ROLE_DELIVERY_DAYS, ROLE_RESPONSE_DAYS}),
    "WARRANTY": frozenset(
        {ROLE_PROJECT_WARRANTY_MONTHS, ROLE_RETENTION_RELEASE_MONTHS, ROLE_RETENTION_MONEY_RATIO}
    ),
    "QUALITY": frozenset({ROLE_PROJECT_WARRANTY_MONTHS}),
    "EVALUATION": frozenset(
        {
            ROLE_SCORE_POINTS,
            ROLE_PAYMENT_RATIO,
            ROLE_BANK_ACCEPTANCE_RATIO,
            ROLE_RETENTION_MONEY_RATIO,
            ROLE_RETENTION_RELEASE_MONTHS,
            ROLE_PRICE,
            ROLE_PRICE_CEILING,
            ROLE_QUANTITY,
            ROLE_PERSON_COUNT,
        }
    ),
    "CONTRACT": frozenset(
        {
            ROLE_PAYMENT_RATIO,
            ROLE_PRICE,
            ROLE_PRICE_CEILING,
            ROLE_PROJECT_WARRANTY_MONTHS,
            ROLE_RETENTION_MONEY_RATIO,
            ROLE_RETENTION_RELEASE_MONTHS,
            ROLE_PERFORMANCE_BOND,
            ROLE_AGENCY_SERVICE_FEE,
            ROLE_QUANTITY,
        }
    ),
    "TECHNICAL": frozenset({ROLE_QUANTITY, ROLE_RESPONSE_DAYS, ROLE_DELIVERY_DAYS}),
    "PERSONNEL": frozenset({ROLE_PERSON_COUNT}),
    "FINANCIAL": frozenset({ROLE_PRICE, ROLE_PRICE_CEILING}),
}

#: roles that are never a bidder review value, whatever the row type
NEVER_USABLE_ROLES: frozenset[str] = NON_REVIEW_ROLES

__all__ = [
    "DISTINCT_MONEY_ROLES",
    "FAMILY_COUNT",
    "FAMILY_DAYS",
    "FAMILY_FORM",
    "FAMILY_MONEY",
    "FAMILY_MONTHS",
    "FAMILY_POINTS",
    "FAMILY_RATIO",
    "FAMILY_TEXT",
    "GENERIC_BUCKETS",
    "LEGACY_ROLE_NAMES",
    "NEVER_USABLE_ROLES",
    "NON_REVIEW_ROLES",
    "ROLES_BY_TYPE",
    "ROLE_AGENCY_SERVICE_FEE",
    "ROLE_BANK_ACCEPTANCE_RATIO",
    "ROLE_BID_VALIDITY_DAYS",
    "ROLE_BOND_AMOUNT",
    "ROLE_BOND_FORM",
    "ROLE_CONTACT",
    "ROLE_CONTACT_INFO",
    "ROLE_DELIVERY_DAYS",
    "ROLE_DURATION_DAYS",
    "ROLE_FAMILY",
    "ROLE_OTHER",
    "ROLE_PAYMENT_RATIO",
    "ROLE_PERFORMANCE_BOND",
    "ROLE_PERSON_COUNT",
    "ROLE_PRICE",
    "ROLE_PRICE_CEILING",
    "ROLE_PROJECT_WARRANTY_MONTHS",
    "ROLE_QUANTITY",
    "ROLE_RESPONSE_BOND",
    "ROLE_RESPONSE_DAYS",
    "ROLE_RETENTION_MONEY_RATIO",
    "ROLE_RETENTION_RELEASE_MONTHS",
    "ROLE_RETENTION_RELEASE_PERIOD",
    "ROLE_SCORE",
    "ROLE_SCORE_POINTS",
    "ROLE_TENDER_DOCUMENT_PRICE",
    "ROLE_TENDER_FEE",
    "ROLE_VALIDITY_DAYS",
    "ROLE_WARRANTY_MONTHS",
    "canonical_role",
    "is_canonical_role",
]
