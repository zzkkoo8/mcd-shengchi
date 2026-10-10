#!/usr/bin/env python3
"""Regression checks for the deterministic now-decision helpers."""

from __future__ import annotations

import unittest

from now_decision import (
    build_decision_card,
    explain_price,
    match_candidates,
    normalize_menu,
    parse_nutrition,
    render_decision_html,
)


NUTRITION = """[3]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:
  巨无霸,null,2146,513,27,26,42,961,171
  无糖可口可乐中杯,null,0,0,0,0,1,35,0
  小杯玉米杯,null,223,53,2,1,7,1,6
  小杯玉米杯,null,223,53,2,1,7,1,6
"""

MENU = {
    "data": {
        "categories": [
            {"name": "人气热卖", "meals": [{"code": "100", "tags": ["辣"]}]},
            {"name": "饮品", "meals": [{"code": "200", "tags": ["冷饮"]}]},
        ],
        "meals": {
            "100": {"name": "麦辣鸡腿汉堡", "currentPrice": "22.5", "originalPrice": "22.5"},
            "200": {"name": "无糖可口可乐中杯", "currentPrice": "9.5", "originalPrice": "9.5"},
            "300": {
                "name": "巨无霸四件套",
                "currentPrice": "32",
                "originalPrice": "58.5",
                "discountType": "随单购麦金卡优惠",
                "canWithOrder": True,
                "withOrder": {"membershipCode": "106"},
            },
        },
    }
}


class NowDecisionTest(unittest.TestCase):
    def test_nutrition_parser_keeps_duplicates_visible(self) -> None:
        rows = parse_nutrition(NUTRITION)
        self.assertEqual(4, len(rows))
        self.assertFalse(rows[2]["duplicate"])
        self.assertTrue(rows[3]["duplicate"])
        self.assertEqual(513, rows[0]["energyKcal"])

    def test_low_calorie_does_not_use_combo_single_item_numbers(self) -> None:
        rows = parse_nutrition(NUTRITION)
        matches = match_candidates(normalize_menu(MENU), rows, "低卡", budget_yuan=30)
        self.assertEqual("无糖可口可乐中杯", matches[0]["name"])
        self.assertEqual("exact-name", matches[0]["nutritionStatus"])
        combo = next(item for item in normalize_menu(MENU) if item["code"] == "300")
        self.assertTrue(combo["requiresWithOrder"])

    def test_price_uses_fen(self) -> None:
        explained = explain_price({"data": {"price": 2690, "discount": 0, "productList": []}})
        self.assertEqual(26.9, explained["payableYuan"])

    def test_decision_card_rejects_unverified_prices(self) -> None:
        card = build_decision_card({
            "sample": True,
            "channel": "pickup",
            "store": {"name": "麦当劳（示例广场店）", "storeCode": "STORE-EXAMPLE"},
            "candidate": {"name": "示例套餐", "code": "MEAL-EXAMPLE", "menuPriceYuan": 29.9},
            "price": {"data": {"price": 2690, "productList": []}},
            "storeCoupon": {"usable": False, "title": "账户早餐券"},
            "unverifiedClaims": [
                {"source": "campaign-copy", "text": "活动页 19.9 元"},
                {"source": "account-coupon", "text": "账户券未核验"},
            ],
        })
        self.assertEqual(26.9, card["payableYuan"])
        self.assertEqual("未证实本店可用", card["storeCoupon"]["status"])
        self.assertEqual("活动文案价，不能下单", card["unverifiedClaims"][0]["label"])
        html = render_decision_html(card)
        self.assertNotIn("<script", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertIn("¥26.90", html)
        self.assertIn("活动文案价", html)

    def test_missing_official_price_is_not_invented(self) -> None:
        card = build_decision_card({
            "store": {"name": "麦当劳（示例广场店）", "storeCode": "STORE-EXAMPLE"},
            "candidate": {"name": "示例套餐", "code": "MEAL-EXAMPLE"},
            "unverifiedClaims": [{"source": "campaign-copy", "text": "文案价 9.9 元"}],
        })
        self.assertIsNone(card["payableYuan"])
        self.assertEqual("not-calculated", card["priceStatus"])


if __name__ == "__main__":
    unittest.main()
