"""
将粗粒度平台 dict / PlatformInfo 转为统一 `StreamingOffer` 列表。
"""

from __future__ import annotations

from typing import Any

from tv_agent.domain.schemas import OfferAccessType, PaymentType, PlatformInfo, StreamingOffer


def payment_to_access_type(pay: PaymentType | str) -> OfferAccessType:
    if isinstance(pay, PaymentType):
        p = pay.value
    else:
        p = (pay or "unknown").lower()
    mapping: dict[str, OfferAccessType] = {
        "free": "free",
        "subscription": "subscription",
        "rental": "rent",
        "purchase": "buy",
        "ad_supported": "free",
        "unknown": "unknown",
    }
    return mapping.get(p, "unknown")


def platform_dict_to_streaming_offer(
    row: dict[str, Any],
    *,
    region: str | None,
    confidence: float = 0.65,
) -> StreamingOffer:
    """单条联网/图节点中的 platform 字典 → StreamingOffer。"""
    raw_pay = row.get("payment_type", "unknown")
    try:
        pay_enum = PaymentType(str(raw_pay).lower())
    except ValueError:
        pay_enum = PaymentType.UNKNOWN
    access = payment_to_access_type(pay_enum)
    official = bool(row.get("official_url"))
    return StreamingOffer(
        provider=str(row.get("platform_name", "") or "unknown"),
        region=region,
        access_type=access,
        quality=None,
        language=[],
        subtitle=[],
        deeplink=row.get("official_url"),
        official=official,
        confidence=confidence,
    )


def platform_dicts_to_offers(
    rows: list[dict[str, Any]],
    *,
    geo_region: str | None = None,
) -> list[StreamingOffer]:
    out: list[StreamingOffer] = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        out.append(
            platform_dict_to_streaming_offer(
                row,
                region=geo_region,
                confidence=0.55 + min(0.35, 0.05 * i),
            )
        )
    return out


def platform_infos_to_offers(
    infos: list[PlatformInfo],
    *,
    geo_region: str | None = None,
) -> list[StreamingOffer]:
    rows = [p.model_dump(mode="json") for p in infos]
    return platform_dicts_to_offers(rows, geo_region=geo_region)


def sort_streaming_offers(
    offers: list[StreamingOffer],
    *,
    confidence_desc: bool = True,
) -> list[StreamingOffer]:
    """按 confidence 排序（默认高置信在前）。"""
    return sorted(offers, key=lambda o: o.confidence, reverse=confidence_desc)
