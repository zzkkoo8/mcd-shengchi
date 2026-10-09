# MCP 调用契约

只记录已在 2026-10-09 用官方 MCP 核对过的契约。新增工具或参数变化时重新核对，不沿用本文件猜测。

## 渠道参数

| 渠道 | beType | orderType | beCode |
|---|---:|---:|---|
| 到店自取 | 1 | 1 | 不传 |
| 得来速 | 5 | 1 | 必传，来自 query-nearby-stores |
| 麦乐送 | 2 | 2 | 必传，来自 delivery-query-stores |
| 企业团餐 | 6 | 2 | 必传，来自 delivery-query-stores |

`query-nearby-stores` 按位置搜索时 `searchType=2`，城市和关键词都必填。收藏搜索使用 `searchType=1`。

## 价格

`query-meals` 的 `currentPrice` 单位是元。`calculate-price` 的金额字段单位是分，展示前除以 100。2026-10-09 在上海黄浦华旭国际大厦餐厅核价「龙焰鸡腿堡三件套」：菜单现价 26.9 元，官方返回 `price=2690`。

## 营养

`list-nutrition-foods` 的 `data` 是自定义文本。同名记录保留首条，重复行标记为 duplicate。套餐名与单品名相同或只命中套餐中的单品时，不得把单品热量当作套餐热量。

## 优惠券

`query-my-coupons` 返回账户券。`query-store-coupons` 才返回指定门店和订单类型下可用的券。2026-10-09 的实测中，账户券适用商品编码与当前菜单商品编码不属于同一编码空间，因此不能直接用账户券商品编码去菜单中找商品。

## 餐品详情

`query-meal-detail` 的餐品参数名是 `code`。传入 `productCode` 会被服务端拒绝。
