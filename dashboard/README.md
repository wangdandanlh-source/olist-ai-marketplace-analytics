# Local dashboard

六页经营分析作品界面：核心经营诊断、增长与留存、商家生命周期、履约与体验、AI 用户之声、策略与验证。静态聚合 JSON，无后端、无认证要求、无外部跟踪器。

本版信息层级按 `Finding → Business Judgment → Recommendation → Validation` 重构：先展示经营结论，再用图表提供证据，最后给出可验证的运营动作。Recommendation 不等同于已实施结果；主动延迟沟通 A/B Test 明确为 DESIGN ONLY。

从此目录执行：

```sh
npm ci
npm run build
npm run preview
```

Node 24 / npm；preview 打印本地地址。不要直接双击 index.html。Vite base 为相对路径，路由使用 hash。页面内筛选仅作用于对应图表，冻结 KPI 不随局部筛选变动。

`npm run build` 包含日期与数据测试。聚合源见 [analysis outputs](../analysis/outputs)。从仓库根目录可执行 `python dashboard/scripts/build_dashboard_data.py` 重建 extract；禁止自动发布行级数据。

[返回项目](../README.md)
