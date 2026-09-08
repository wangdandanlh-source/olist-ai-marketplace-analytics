# Metric dictionary

| Metric | Definition / denominator | Window / caution |
|---|---|---|
| Merchandise GMV | sum item price; 12,342,450.49 BRL | core delivered; excludes freight, not revenue |
| Delivered orders | distinct order_id; 89,860 | purchase 2017-01 through 2018-07 |
| Purchase frequency | orders / distinct customer_unique_id | same core scope |
| AOV | merchandise GMV / orders | BRL |
| July YoY | July 2018 GMV / July 2017 GMV - 1; 80.22% | mathematical comparison |
| Contribution shares | users 80.00%; frequency -1.49%; AOV 21.49% | Shapley mathematical shares, not causal |
| Observed MQL conversion | 842 / 8,000 = 10.53% | snapshot, not mature cohort conversion |
| Seller match | 380 / 842 = 45.13% | selection limits downstream results |
| Seller 90D GMV | median 694.65, mean 2,376.19 BRL; n=124 | common mature 90D |
| Inactivity signal | 41 / 124 = 33.06% | no observed orders in final 30D, not churn |
| Repeat | 2,609 / 86,960 = 3.00% | >=2 core orders |
| Mature repurchase | 978, 1,230, 1,409 / 68,617 | common 30/60/90D; 1.43/1.79/2.05% |
| ≥24h sensitivity | 870 / 68,617 = 1.27% | 90D; elapsed time >=24h between purchase timestamps; not ground truth |
| Late rate | 6,138 / 89,852 = 6.83% | valid delivered and estimated dates |
| Rating means | all on-time 4.284, late 2.224 | canonical rating per order |
| After-answer rating means | on-time 4.284, late 3.688 | answer timestamp at/after delivery |
| Adjusted OR | 2.31; CI 2.04–2.62 | after-answer low-score <=2 logistic model |
| AI corpus | 40,748 canonical written reviews | all dates; not only core window |
| Waiting late rates | 1,546/2,752; 96/1,298; baseline 742/33,446 | 56.18%; 7.40%; 2.22%; latter two after-delivery answer |
| Mixed / Other | 9,013 / 14,375 = 62.70% | primary score<=3 corpus, includes broad product cluster |

Displayed values use ordinary half-up rounding; frozen underlying values remain full precision. Data lineage is provided in dashboard/data/sources.json and accepted aggregate CSVs in analysis/outputs.
