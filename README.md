# 省吃

账户里有券，不等于这家店能用。活动页写的价格，也不等于现在能下单的价格。

省吃面向临时决定吃麦当劳的人。它先查当前门店和菜单，再区分门店可用券与账户券，最后只把官方核价当成可下单价。没有官方核价时，它不会用文案价补一个“大概多少钱”。

本项目是麦当劳程序员创意开发大赛参赛作品，不是麦当劳官方产品。输出仅供参考，不构成营养或医疗建议。

## 30 秒看懂

无需 Token，用脱敏样例生成一张决策卡：

```bash
python3 scripts/now_decision.py render-card \
  --input examples/decision-card.sample.json \
  --html examples/decision-card.sample.html
```

打开 `examples/decision-card.sample.html`。样例里的门店、餐品和券都是虚构数据；2690 分会被确定性地换算成 26.90 元，活动文案价仍标为不能下单。

真实使用时，在已启用麦当劳 MCP 的对话中说：

```text
我现在在上海人民广场，预算 30 元，想吃辣的，先不要下单。
```

## 它解决什么

| 常见误判 | 省吃怎么处理 |
|---|---|
| 账户券当作本店可用券 | 只把 `query-store-coupons` 的结果标为已验证 |
| 活动页价格当作订单价 | 文案价单独列出，不能替代 `calculate-price` |
| 菜单现价当作最终支付价 | 菜单价只做预算预筛，支付价以官方核价为准 |
| 套餐套用同名单品热量 | 名称不精确命中时不展示热量 |

## 目标用户

- 现在想吃，但还没决定店、套餐和预算的食客。
- 需要确认优惠券在当前门店是否真能用的食客。
- 需要在下单前核对官方价格，并避免误用热量数据的食客。

## 安装

1. 在 [麦当劳 MCP 开放平台](https://open.mcd.cn/mcp) 用手机号登录并申请 MCP Token。
2. 在 WorkBuddy 的自定义连接器中配置 `mcp-config.example.json`，由客户端注入 `${MCD_MCP_TOKEN}`。不要把真实 Token 写入仓库。
3. 信任并启用 `mcd-mcp` 后新建对话。
4. 将本仓库作为 Skill 使用，或把 `SKILL.md` 放入 WorkBuddy Skill 目录。

## 本地检查

确定性脚本不访问网络，也不读取凭证：

```bash
python3 scripts/now_decision.py channel --name pickup
python3 -m unittest scripts/test_now_decision.py
```

价格换算、营养精确匹配和“没有官方核价就不编造价格”都有回归测试。

## 边界

- 不自动下单、取消订单、领券、兑换、抽奖或新增地址。
- 门店、菜单或核价任一失败时停止推荐，不用上次结果或模型记忆补齐。
- 随单购优惠只有用户明确同意购买对应卡时，才展示为可达成价格。
- 决策卡可以截图转发；样例卡会明确标注“不是当前报价”。
