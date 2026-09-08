# Methodology

业务链路为商家获取、激活、交易、客户价值、履约和评价。核心经营窗口 [2017-01-01, 2018-08-01)，订单状态为 delivered；金额为商品行 price 的整数分汇总，除以 100 得 BRL，不含运费，也不等同平台收入。

items 与 payments 各自先聚合至订单再 JOIN，防止多子表笛卡尔重复。代表评分与 canonical 正文保留不同用途及样本范围，具体确定性选择规则见 [SQL](../analysis/sql/metric_layer.sql) 和 [VOC SQL](../analysis/sql/session3_corpus.sql)。

July YoY 分解沿用已验收 Shapley 数学分解；贡献份额合计 100%，不识别因果。Seller 只比较匹配且共同成熟窗口；客户复购将同一客户的严格较晚订单与购买时间间隔 ≥24h敏感性分开。

履约迟到为签收日期晚于预计日期，缺少有效日期者不进入迟到率分母；签收后作答按 review_answer_timestamp >= order_delivered_customer_date 判断。低评分 <=2。Logistic GLM 控制品类、州、月份、订单金额与运费负担，标准误按客户聚类；报告签收后作答模型 OR 2.31，非全部评价模型，也非因果效应。

报告与 Dashboard 从同一已验收聚合层读取，保留数据来源文件 SHA-256；报告重新生成静态图，不贴整页 Dashboard 截图。 [指标字典](metric_dictionary.md)、[AI 方法](ai_voc_method.md)、[限制](limitations.md)。

“购买时间间隔 ≥24h”指两次购买时间戳的 elapsed time >=24h（elapsed_days >=1），不是跨自然日。
