#!/usr/bin/env python3
"""Deterministic helpers for the McDonald's now-decision skill.

The script never calls the network and never reads credentials. Callers pass
already retrieved MCP payloads. Nutrition parsing, menu normalization, intent
matching, and fen-to-yuan conversion are deterministic so an agent does not
rebuild them on every request.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any


NUTRITION_FIELDS = (
    "productName",
    "nutritionDescription",
    "energyKj",
    "energyKcal",
    "protein",
    "fat",
    "carbohydrate",
    "sodium",
    "calcium",
)

CHANNEL_RULES = {
    "pickup": {"beType": 1, "orderType": 1, "beCodeRequired": False, "label": "到店自取"},
    "drive": {"beType": 5, "orderType": 1, "beCodeRequired": True, "label": "得来速"},
    "delivery": {"beType": 2, "orderType": 2, "beCodeRequired": True, "label": "麦乐送"},
    "group": {"beType": 6, "orderType": 2, "beCodeRequired": True, "label": "企业团餐"},
}

INTENT_KEYWORDS = {
    "low_calorie": ("低卡", "减脂", "热量低", "清淡", "控热量"),
    "high_protein": ("高蛋白", "蛋白质", "蛋白"),
    "budget": ("便宜", "省钱", "预算", "划算"),
    "spicy": ("辣", "麦辣", "韩式"),
    "beef": ("牛肉", "牛堡", "巨无霸", "安格斯"),
    "chicken": ("鸡", "炸鸡", "麦乐鸡"),
    "fish": ("鱼", "鳕鱼"),
    "coffee": ("咖啡", "美式", "奶铁"),
    "dessert": ("甜品", "麦旋风", "冰淇淋", "雪糕"),
}


def parse_nutrition(payload: str) -> list[dict[str, Any]]:
    """Parse the custom nutrition payload into unique records.

    Official format starts with ``[count]{field list}:`` and continues with
    indented comma-separated rows. Duplicate names keep the first record and
    are reported rather than silently merged into a false average.
    """
    text = payload.strip()
    if not text:
        return []
    header_match = re.match(r"^\[(\d+)\]\{([^}]+)\}:\s*", text)
    if not header_match:
        raise ValueError("nutrition payload is not in the documented custom format")
    fields = [item.strip() for item in header_match.group(2).split(",")]
    if fields != list(NUTRITION_FIELDS):
        raise ValueError("nutrition field order changed; refuse to guess columns")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_line in text[header_match.end():].splitlines():
        line = raw_line.strip().rstrip(",")
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != len(fields):
            raise ValueError(f"nutrition row has {len(parts)} columns, expected {len(fields)}")
        record: dict[str, Any] = {"duplicate": False}
        for field, value in zip(fields, parts):
            if field in {"productName", "nutritionDescription"}:
                record[field] = None if value == "null" else value
            else:
                record[field] = _number(value)
        name = str(record["productName"])
        if name in seen:
            record["duplicate"] = True
        else:
            seen.add(name)
        rows.append(record)
    return rows


def normalize_menu(menu: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten a query-meals payload without inventing missing prices."""
    data = menu.get("data", menu)
    meals = data.get("meals", {})
    categories = data.get("categories", [])
    category_by_code: dict[str, list[str]] = {}
    tags_by_code: dict[str, list[str]] = {}
    for category in categories:
        name = str(category.get("name", "")).replace("\n", "")
        for item in category.get("meals", []):
            code = str(item.get("code", ""))
            if not code:
                continue
            category_by_code.setdefault(code, [])
            if name and name not in category_by_code[code]:
                category_by_code[code].append(name)
            tags_by_code.setdefault(code, [])
            for tag in item.get("tags", []):
                if tag not in tags_by_code[code]:
                    tags_by_code[code].append(tag)

    normalized = []
    for code, detail in meals.items():
        current = _optional_number(detail.get("currentPrice"))
        original = _optional_number(detail.get("originalPrice"))
        normalized.append({
            "code": str(code),
            "name": detail.get("name", ""),
            "currentPriceYuan": current,
            "originalPriceYuan": original,
            "discountType": detail.get("discountType"),
            "requiresWithOrder": bool(detail.get("canWithOrder")) and bool(detail.get("withOrder")),
            "categories": category_by_code.get(str(code), []),
            "tags": tags_by_code.get(str(code), []),
        })
    return normalized


def match_candidates(
    menu_items: list[dict[str, Any]],
    nutrition_rows: list[dict[str, Any]],
    intent: str,
    budget_yuan: float | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank menu items and attach nutrition only on an exact name match."""
    keywords = _intent_keywords(intent)
    nutrition_by_name = {}
    for row in nutrition_rows:
        if not row.get("duplicate"):
            nutrition_by_name.setdefault(row["productName"], row)

    ranked = []
    for item in menu_items:
        if item.get("currentPriceYuan") is None:
            continue
        if budget_yuan is not None and item["currentPriceYuan"] > budget_yuan:
            continue
        searchable = " ".join([item["name"], *item.get("tags", []), *item.get("categories", [])])
        score = sum(3 for word in keywords if word and word in searchable)
        if "budget" in _intent_labels(intent):
            score += max(0, 20 - item["currentPriceYuan"]) / 10
        if "low_calorie" in _intent_labels(intent) and item["name"] in nutrition_by_name:
            kcal = nutrition_by_name[item["name"]]["energyKcal"]
            if isinstance(kcal, (int, float)):
                score += max(0, 600 - kcal) / 100
        if score <= 0 and keywords:
            continue
        nutrition = nutrition_by_name.get(item["name"])
        ranked.append({
            "code": item["code"],
            "name": item["name"],
            "menuPriceYuan": item["currentPriceYuan"],
            "discountType": item.get("discountType"),
            "requiresWithOrder": item.get("requiresWithOrder", False),
            "score": round(score, 2),
            "nutrition": None if nutrition is None else {
                "match": "exact-name",
                "energyKcal": nutrition["energyKcal"],
                "protein": nutrition["protein"],
                "fat": nutrition["fat"],
                "carbohydrate": nutrition["carbohydrate"],
                "sodium": nutrition["sodium"],
                "warning": "单品营养不能代表同名套餐",
            },
            "nutritionStatus": "exact-name" if nutrition else "unmatched",
        })
    ranked.sort(key=lambda row: (-row["score"], row["menuPriceYuan"], row["name"]))
    return ranked[:limit]


def explain_price(price_payload: dict[str, Any]) -> dict[str, Any]:
    """Convert an official calculate-price payload from fen to yuan."""
    data = price_payload.get("data", price_payload)
    return {
        "payableYuan": _fen_to_yuan(data.get("price")),
        "originalYuan": _fen_to_yuan(data.get("originalPrice")),
        "discountYuan": _fen_to_yuan(data.get("discount")),
        "productYuan": _fen_to_yuan(data.get("productPrice")),
        "deliveryYuan": _fen_to_yuan(data.get("deliveryPrice")),
        "packingYuan": _fen_to_yuan(data.get("packingPrice")),
        "tablewareYuan": _fen_to_yuan(data.get("tablewarePrice")),
        "products": [
            {
                "code": item.get("productCode"),
                "name": item.get("productName"),
                "quantity": item.get("quantity"),
                "subtotalYuan": _fen_to_yuan(item.get("subtotal")),
            }
            for item in data.get("productList", [])
        ],
        "takeWays": [
            {"code": item.get("code"), "title": item.get("title")}
            for item in data.get("takeWayList", [])
        ],
        "unit": "yuan",
        "sourceUnit": "fen",
    }


def channel_params(channel: str) -> dict[str, Any]:
    if channel not in CHANNEL_RULES:
        raise ValueError(f"unknown channel: {channel}")
    return dict(CHANNEL_RULES[channel])


PRICE_SOURCE_LABELS = {
    "official-calculate-price": "官方核价",
    "menu-price": "菜单现价，尚未核价",
    "campaign-copy": "活动文案价，不能下单",
    "account-coupon": "账户券，不证明本店可用",
}


def build_decision_card(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a shareable decision card from already retrieved facts.

    The function does not call MCP and does not invent a payable price. A
    campaign price or an account coupon can be displayed only as an unverified
    claim. The payable amount exists only when calculate-price supplied it.
    """
    channel = channel_params(str(payload.get("channel", "pickup")))
    store = payload.get("store") or {}
    candidate = payload.get("candidate") or {}
    price = payload.get("price")
    coupon = payload.get("storeCoupon") or {}
    claims = payload.get("unverifiedClaims") or []
    if not store.get("name") or not store.get("storeCode"):
        raise ValueError("decision card requires a store name and storeCode")
    if not candidate.get("name") or not candidate.get("code"):
        raise ValueError("decision card requires a candidate name and code")

    explained = explain_price(price) if price else None
    payable = None if explained is None else explained["payableYuan"]
    nutrition = candidate.get("nutrition")
    nutrition_status = candidate.get("nutritionStatus", "unmatched")
    if nutrition_status != "exact-name":
        nutrition = None
    coupon_status = "本店可用" if coupon.get("usable") is True else "未证实本店可用"
    verified = []
    if explained is not None:
        verified.append("官方核价")
    if coupon.get("usable") is True:
        verified.append("门店可用券")
    if nutrition_status == "exact-name":
        verified.append("营养名称精确命中")

    return {
        "title": "省吃决策卡",
        "sample": bool(payload.get("sample")),
        "disclaimer": "样例数据，不是当前门店报价" if payload.get("sample") else "仅供参考，不构成营养或医疗建议",
        "channel": channel["label"],
        "store": {
            "name": store["name"],
            "storeCode": str(store["storeCode"]),
            "distance": store.get("distance"),
            "openHours": store.get("openHours"),
        },
        "candidate": {
            "code": str(candidate["code"]),
            "name": candidate["name"],
            "menuPriceYuan": candidate.get("menuPriceYuan"),
            "requiresWithOrder": bool(candidate.get("requiresWithOrder")),
        },
        "payableYuan": payable,
        "priceStatus": "official-calculate-price" if explained else "not-calculated",
        "priceBreakdown": explained,
        "nutrition": nutrition,
        "nutritionStatus": nutrition_status,
        "storeCoupon": {
            "status": coupon_status,
            "title": coupon.get("title"),
            "usable": coupon.get("usable") is True,
        },
        "verified": verified,
        "unverifiedClaims": [
            {
                "source": item.get("source"),
                "label": PRICE_SOURCE_LABELS.get(str(item.get("source")), "未验证"),
                "text": item.get("text"),
            }
            for item in claims
        ],
        "nextAction": "确认前不领券、不下单、不支付",
    }


def render_decision_html(card: dict[str, Any]) -> str:
    """Render one self-contained card. No remote fonts, scripts, or images."""
    payable = "尚未官方核价" if card["payableYuan"] is None else f"¥{card['payableYuan']:.2f}"
    menu_price = card["candidate"].get("menuPriceYuan")
    menu_text = "菜单价未提供" if menu_price is None else f"菜单现价 ¥{float(menu_price):.2f}"
    nutrition = card.get("nutrition") or {}
    kcal = "热量未精确命中" if not nutrition else f"{nutrition.get('energyKcal')} kcal"
    claims = "".join(
        f"<li><strong>{_escape(item['label'])}</strong>：{_escape(item.get('text') or '')}</li>"
        for item in card["unverifiedClaims"]
    ) or "<li>没有额外的未验证价格声明</li>"
    sample = "<p class=\"sample\">脱敏样例 · 不能当作今日报价</p>" if card["sample"] else ""
    with_order = "需随单购后才可能达到展示优惠" if card["candidate"]["requiresWithOrder"] else "不依赖随单购"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>省吃决策卡</title>
<style>
:root {{ color-scheme: light; }}
body {{ margin: 0; background: #f6f1e8; color: #241c15; font: 16px/1.5 "PingFang SC", "Noto Sans SC", sans-serif; }}
main {{ max-width: 440px; margin: 24px auto; padding: 24px; background: #fffaf3; border: 1px solid #e6d7c3; border-radius: 18px; }}
h1 {{ margin: 0 0 4px; font-size: 28px; letter-spacing: .04em; }}
.sample, .note {{ color: #8a5a12; }}
.payable {{ margin: 18px 0; font-size: 42px; font-weight: 750; color: #da291c; }}
dl {{ display: grid; grid-template-columns: 92px 1fr; gap: 8px 12px; margin: 16px 0; }}
dt {{ color: #6d6258; }}
dd {{ margin: 0; }}
ul {{ padding-left: 18px; }}
</style>
</head>
<body>
<main>
  {sample}
  <h1>省吃</h1>
  <p>账户券和活动文案价，都不是可下单价。</p>
  <p class="payable">{_escape(payable)}</p>
  <dl>
    <dt>门店</dt><dd>{_escape(card["store"]["name"])}</dd>
    <dt>渠道</dt><dd>{_escape(card["channel"])}</dd>
    <dt>候选</dt><dd>{_escape(card["candidate"]["name"])}</dd>
    <dt>菜单价</dt><dd>{_escape(menu_text)} · {_escape(with_order)}</dd>
    <dt>热量</dt><dd>{_escape(kcal)}</dd>
    <dt>门店券</dt><dd>{_escape(card["storeCoupon"]["status"])}</dd>
  </dl>
  <h2>不能直接相信</h2>
  <ul>{claims}</ul>
  <p class="note">{_escape(card["nextAction"])}。{_escape(card["disclaimer"])}</p>
</main>
</body>
</html>
"""


def _escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _intent_labels(intent: str) -> set[str]:
    labels = set()
    for label, words in INTENT_KEYWORDS.items():
        if any(word in intent for word in words):
            labels.add(label)
    return labels


def _intent_keywords(intent: str) -> list[str]:
    words = []
    for label in _intent_labels(intent):
        words.extend(INTENT_KEYWORDS[label])
    compact = re.sub(r"\s+", "", intent)
    if compact and compact not in words:
        words.append(compact)
    return words


def _number(value: str) -> int | float | None:
    if value == "null" or value == "":
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    raise ValueError(f"nutrition numeric field is not numeric: {value}")


def _optional_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _fen_to_yuan(value: Any) -> float | None:
    if value is None:
        return None
    return round(int(value) / 100, 2)


def _load_json(path: str) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic now-decision helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    nutrition = subparsers.add_parser("parse-nutrition")
    nutrition.add_argument("--input", required=True)

    menu = subparsers.add_parser("normalize-menu")
    menu.add_argument("--input", required=True)

    match = subparsers.add_parser("match")
    match.add_argument("--menu", required=True)
    match.add_argument("--nutrition", required=True)
    match.add_argument("--intent", required=True)
    match.add_argument("--budget", type=float)
    match.add_argument("--limit", type=int, default=5)

    price = subparsers.add_parser("explain-price")
    price.add_argument("--input", required=True)

    channel = subparsers.add_parser("channel")
    channel.add_argument("--name", required=True, choices=sorted(CHANNEL_RULES))

    card = subparsers.add_parser("render-card")
    card.add_argument("--input", required=True)
    card.add_argument("--html")

    args = parser.parse_args()
    if args.command == "parse-nutrition":
        payload = open(args.input, encoding="utf-8").read()
        result = parse_nutrition(payload)
    elif args.command == "normalize-menu":
        result = normalize_menu(_load_json(args.input))
    elif args.command == "match":
        result = match_candidates(
            normalize_menu(_load_json(args.menu)),
            parse_nutrition(open(args.nutrition, encoding="utf-8").read()),
            args.intent,
            args.budget,
            args.limit,
        )
    elif args.command == "explain-price":
        result = explain_price(_load_json(args.input))
    elif args.command == "render-card":
        result = build_decision_card(_load_json(args.input))
        if args.html:
            with open(args.html, "w", encoding="utf-8") as handle:
                handle.write(render_decision_html(result))
    else:
        result = channel_params(args.name)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
