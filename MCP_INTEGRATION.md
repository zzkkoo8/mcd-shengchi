# MCP 集成说明

## 使用的服务

- Server：麦当劳中国官方远程 MCP Server，`mcd-mcp`
- 地址：`https://mcp.mcd.cn`
- 协议：Streamable HTTP
- 身份：`Authorization: Bearer ${MCD_MCP_TOKEN}`

## 实际调用的 Tool

| Tool | 用途 | 实测结果 |
|---|---|---|
| now-time-info | 确认当前决策时间 | 2026-10-09 16:48:29 GMT+08 |
| query-nearby-stores | 按城市和关键词查到店门店 | 上海人民广场返回营业门店及 storeCode |
| query-meals | 获取当前门店可售餐品和菜单价 | 上海黄浦华旭国际大厦餐厅返回分类、编码和现价 |
| query-store-coupons | 校验当前门店真实可用券 | 返回门店券、券 ID 和适用商品 |
| query-my-coupons | 查看账户券资产 | 返回账户券，但不能替代门店可用性 |
| available-coupons | 查看可领券 | 返回可领取状态，不自动领取 |
| list-nutrition-foods | 获取营养原始数据 | 返回 160 条自定义文本，不是 JSON |
| campaign-calendar | 提示当日活动 | 返回活动文案，文案价格不作为订单价 |
| calculate-price | 官方核价 | 龙焰鸡腿堡三件套返回 2690 分，即 26.9 元 |
| query-meal-detail | 查看套餐组成 | 参数名核对为 code；错误参数会被拒绝 |

写入类 Tool `create-order`、`cancel-order`、`auto-bind-coupons`、`delivery-create-address`、`mall-create-order`、`draw-lottery`、`party-order-create` 已在官方工具列表中发现，但本项目不自动调用。

## 调用流程

1. 确认渠道并生成 beType、orderType、beCode 规则。
2. 查询门店，保留 storeCode；需要时保留 beCode。
3. 查询当前菜单，脚本把分类、标签和价格归一化。
4. 需要热量时解析营养文本，只对精确同名餐品附加营养。
5. 需要省钱时查询门店可用券，账户券只作资产说明。
6. 对一个候选调用官方核价，脚本把分换算成元。
7. 输出决策卡。用户明确要求前不创建订单。

## 业务价值

「省吃」解决的是临时吃麦当劳时如何少花钱且不看错价：这家店现在能不能吃、哪张券真能用、价格和热量是否可接受。项目把这四件事串成一次决策，并明确区分菜单价、活动文案价、账户券和官方核价，避免把不可用信息说成可下单事实。
