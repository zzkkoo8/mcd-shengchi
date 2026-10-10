---
name: mcd-now-decision
description: 在用户想省着吃麦当劳、按预算选餐、核对门店可用券和官方价格时使用。基于麦当劳 MCP 完成选店、选品、门店券校验和核价，不自动领券、下单或支付。
---

# 省吃

把「现在想吃麦当劳」收成一条可核对的决策：哪家店、现在卖什么、哪张券在这家店真能用、官方核价是多少。菜单价、活动文案价和卡包券都不能直接当成可下单价。

## 触发

用户提到现在吃、附近麦当劳、选套餐、预算、热量、门店可用券或下单前核价时使用。只问活动日历、积分抽奖或商城兑换时不使用本 Skill。

## 流程

1. 确认渠道。未说明时默认到店自取。用 `scripts/now_decision.py channel --name pickup|drive|delivery|group` 取得 `beType`、`orderType` 和 `beCode` 规则。
2. 选店。到店或得来速调用 `query-nearby-stores`；外送或团餐先调用 `delivery-query-addresses`，无地址时停止并询问，不调用 `delivery-create-address`。展示门店名称、距离、营业时间和完整 `storeCode`。得来速、外送、团餐还必须展示 `beCode`。
3. 查当前菜单。调用 `query-meals`。到店自取不传 `beCode`。把返回 JSON 保存为临时文件，运行 `scripts/now_decision.py normalize-menu --input <file>`。
4. 匹配候选。需要热量时先调用 `list-nutrition-foods`，把原始 `data` 字符串保存为临时文件。运行 `scripts/now_decision.py match --menu <menu.json> --nutrition <nutrition.txt> --intent "<用户原话>" --budget <元>`。预算按菜单现价预筛，最终价格仍以核价为准。
5. 校验门店券。用户要省钱时调用 `query-store-coupons`。`query-my-coupons` 和 `available-coupons` 只说明账户资产或可领状态，不证明当前门店可用。账户券的商品编码与当前菜单编码不一致时，不得把账户券直接套到菜单商品上。
6. 官方核价。对用户选中的一个候选调用 `calculate-price`。套餐使用 `query-meal-detail` 返回的默认组合，参数名是 `code`，不是 `productCode`。运行 `scripts/now_decision.py explain-price --input <price.json>`。向用户展示元，不展示分。
7. 生成决策卡。把已核实的门店、候选、官方核价和门店券写入临时 JSON，运行 `scripts/now_decision.py render-card --input <card.json> --html <card.html>`。活动文案价和账户券只能放入 `unverifiedClaims`。没有 `calculate-price` 结果时不得填写 `price`。样例只能来自 `examples/decision-card.sample.json`，并保留 `sample: true`。用户明确要求下单前停止。下单、领券、取消、兑换、抽奖和新增地址都必须单独确认。

## 硬边界

- 不调用 `create-order`、`cancel-order`、`auto-bind-coupons`、`mall-create-order`、`draw-lottery`、`party-order-create`、`delivery-create-address`，除非用户在看到决策卡后明确要求，并再次确认具体动作。
- 营养数据是 `[count]{字段}:` 加缩进逗号行，不是 JSON。只接受脚本解析结果。
- 营养名称精确命中才可引用热量。套餐命中同名单品时标注「仅单品口径」，不得把单品热量说成套餐热量。
- 零热量饮料可以命中低卡饮品，但不能作为一餐的主食推荐。
- 活动日历中的价格是营销文案。可调用 `campaign-calendar` 提示今日活动，但不得用文案价格替代 `calculate-price`。
- 随单购优惠价只有用户明确同意随单购买对应卡时才可展示为可达成价格，否则展示原价路径。
- 不输出 Token、券码、会员号、手机号或地址。配置只使用环境变量占位符。

## 失败处理

门店、菜单或核价任一调用失败时，停止推荐并说明失败环节。不得用上一次结果、活动文案或模型记忆补齐价格、库存和券可用性。
