# AI-Powered Marketplace Operations & Seller Growth Analytics

使用 Olist 真实 Marketplace 数据，结合 SQL/Python、经营分析、履约分析与 AI-assisted VOC，从“发现问题”进一步走到“经营判断 → 策略建议 → 验证设计”。

[Live Dashboard](https://wangdandanlh-source.github.io/olist-ai-marketplace-analytics/) · [Dashboard Source](dashboard/README.md) · [Methodology](docs/methodology.md) · [A/B Design](docs/experiment_design.md)

## Project overview / Business questions

本项目围绕三个核心经营问题展开：

1. **Growth & Retention**：GMV 增长以后，用户有没有留下来？
2. **Seller Lifecycle**：商家签约以后，是否真正进入持续经营？
3. **Fulfillment & CX**：用户为什么对履约不满意，哪些环节可以被运营干预？

AI VOC 作为辅助诊断层，用于从葡语评论中发现结构化订单数据难以直接表达的体验主题，再回到履约与评分数据进行验证。

## Core business findings → actions

- **增长质量**：2018-07 商品 GMV 同比 +80.22%，其中用户规模数学贡献约 80%；全期观测复购仅 3.00%，约 97% 用户仅一单。**Recommendation：首购 → 二购激活**，优先针对高价值一次性用户设计 30/60/90D 差异化触达，并以前瞻实验验证。
- **Seller 成长**：8,000 MQL → 842 Deals；仅 380 / 842 成交 Seller 可匹配订单，因此不据此判断渠道 ROI。共同成熟 90D Seller 中，GMV 中位数 694.65 BRL、均值 2,376.19 BRL；41 / 124 最后 30D 无记录订单。**Recommendation：建立 Seller 30/60/90D 生命周期运营**；41 / 124 仅作为 inactivity signal，不称为 churn。
- **履约与体验**：整体迟到率 6.83%；签收后作答样本中，迟到与低评分仍存在明显关联，调整 OR 2.31（95% CI 2.04-2.62），但不作因果解释。AI 分析 40,748 条 canonical 正文后进一步暴露等待/未收到等体验主题。**Recommendation：主动延迟沟通**，并通过随机 A/B Test 验证。

## Dashboard

[Live Dashboard](https://wangdandanlh-source.github.io/olist-ai-marketplace-analytics/) 通过 GitHub Pages 部署，当前按业务故事重构为六页：

- 核心经营诊断：3 个问题 → 3 套行动
- 增长与留存：增长来源、复购与首购后二次转化
- 商家生命周期：Acquisition → Conversion → Activation → Growth → Inactivity Signal
- 履约与体验：迟到 → 评分关联 → VOC → 可干预机会
- AI 用户之声：Structured Data + AI-assisted VOC → Business Validation
- 策略与验证：3 Strategies + A/B Test Design

Dashboard 先展示经营判断，再提供数据证据；技术方法与限制下沉至文档层，避免让算法盖过业务结论。

## Experiment design

主动延迟沟通实验为 **DESIGN ONLY**，没有运行真实实验，也不声称任何策略提升。建议对首次超过原 ETA、仍未签收且符合联系条件的客户进行 1:1 随机；主指标为 14 天内等待/未收到相关客户主动联系率（ITT），同时监控低评分、取消、投诉、退订、通知成本与 ETA 准确性。完整设计见 [docs/experiment_design.md](docs/experiment_design.md)。

## Data sources / Metric framework

数据来自 Olist Brazilian E-Commerce Public Dataset 与 Marketing Funnel by Olist；[来源与许可](DATA_SOURCES.md)。GMV = Customers × Purchase Frequency × AOV；[指标字典](docs/metric_dictionary.md)说明粒度、分母、窗口和例外。

## Analysis / AI VOC

[SQL 与 Python](analysis/README.md)提供可检查的分析流程。[AI 方法](docs/ai_voc_method.md)使用多语言 MiniLM、语义聚类、AI 辅助主题命名与结构化验证。AI 是探索性发现工具，不是经过人工 Gold Set 验证的分类器；原始数据、逐条正文、翻译样本、模型权重及数据库不分发。

## Tech stack / Reproduce

SQL · Python · Statistical Analysis · React · ECharts · AI/NLP · Multilingual Embeddings

```sh
cd dashboard
npm ci
npm run build
npm run preview
```

使用 Node 24；Dashboard 聚合数据已提供，无需原始数据或凭据。[分析复现](analysis/README.md)说明 Python 3.12、数据目录与执行顺序。

## Limitations / License

[主要限制](docs/limitations.md)包括匹配缺失、观察截尾、低复购、Review self-selection、评价时点和无 Human Gold Set。[NOTICE](NOTICE.md)区分代码、数据派生物及第三方依赖；[Security](SECURITY.md)说明静态产品的数据边界。
