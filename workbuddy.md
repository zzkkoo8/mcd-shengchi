# WorkBuddy 开发上下文

本文件记录使用 WorkBuddy 完成本参赛项目的开发上下文，用于活动要求的 WorkBuddy 使用核验。不包含 MCP Token、券码、手机号、地址或其他个人敏感信息。

## 会话目标

参加麦当劳程序员创意开发大赛，基于官方麦当劳 MCP 开发一个可复用 Skill，并按活动规则准备公开仓库与报名材料。

## 已完成的准备

- 阅读活动仓库 README、activityGuidelines 和 CONTEST_DECLARATION。
- 确认参赛仓库必须属于 GitHub 个人账户且公开。
- 用户完成手机号验证和 MCP Token 激活。
- 在 WorkBuddy 用户级 MCP 配置写入 mcd-mcp，并完成信任和启用。
- 当前会话加载 mcd-mcp 后，调用 now-time-info 成功。

## 场景选择

项目名称为「省吃」。选择临时省钱决策而不是全天配餐或抽奖。食客最常见的决策是选店、选当前可售餐、确认门店券和官方价格。活动文案、账户券和菜单价都不能单独代表可下单事实。

## 开发与验证

- 初始化 Skill 目录 mcd-now-decision。
- 编写确定性脚本，处理营养自定义文本、菜单归一化、候选匹配和分到元换算。
- 运行单元测试，覆盖重复营养行、低卡误推荐和价格单位。
- 使用官方 MCP 只读调用核对门店、菜单、账户券、可领券、活动日历和官方核价。
- 确认 query-meal-detail 的餐品参数名是 code。
- 未调用创建订单、领券、取消订单、兑换、抽奖或新增地址。

## 提交范围

仓库包含 README.md、CONTEST_DECLARATION.md、MCP_INTEGRATION.md、mcp-config.example.json、SKILL.md、references、scripts 和本文件。配置示例只使用环境变量占位符。
