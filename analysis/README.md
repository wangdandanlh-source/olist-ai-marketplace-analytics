# Analysis reproduction

Python 3.12；pandas/numpy 用于数据层，scipy/statsmodels 用于统计检验，scikit-learn/joblib/threadpoolctl 用于聚类，onnxruntime/tokenizers 用于本地多语言向量。直接依赖见 requirements.txt；没有使用全环境 pip freeze。

从仓库根目录，在私人工作副本中执行：

```sh
python -m venv .venv
# Activate this environment using your shell, then:
python -m pip install -r analysis/requirements.txt
python analysis/src/prepare_local.py
```

从 [官方数据来源](../DATA_SOURCES.md)自行取得文件；本次未重新下载数据。原始目录：

```text
analysis/data/raw/brazilian-ecommerce/
  olist_customers_dataset.csv
  olist_geolocation_dataset.csv
  olist_orders_dataset.csv
  olist_order_items_dataset.csv
  olist_order_payments_dataset.csv
  olist_order_reviews_dataset.csv
  olist_products_dataset.csv
  olist_sellers_dataset.csv
  product_category_name_translation.csv
analysis/data/raw/marketing-funnel-olist/
  olist_closed_deals_dataset.csv
  olist_marketing_qualified_leads_dataset.csv
```

```sh
python analysis/src/build.py
python analysis/src/session2_analysis.py
python analysis/src/session3_prepare.py
python analysis/src/session3_download_model.py
python analysis/src/session3_embed.py
python analysis/src/session3_cluster.py
python analysis/src/session3_select.py --k 8
python analysis/src/session3_taxonomy.py
python analysis/src/session3_validate.py
```

先检查前一阶段 QA，任何 FAIL 应停止，不以新结果替换已验收结论。build.py 使用随附的最小官方文件大小元数据和快照行数做验证，写入本地 data/interim、data/processed；原始数据不被修改。模型下载脚本仅在明确执行时访问模型站点，未在 Session 6 运行；模型 revision 固定在源文件中。

Session 3 的 embed 阶段旧 manifest 记录 sklearn 1.9.0，而已验收聚类采用后续稳定环境 1.7.2。这里固定 1.7.2 供聚类使用；向量推理使用 ONNX，不使用 sklearn，fallback 必须停下复核，不能当作已验收 MiniLM 的复现。跨硬件/数值库可能产生差异，只有核对 QA 与冻结指标后才可判定一致。

主题命名包含已冻结簇映射；这是 AI 决策的重放，不是再次调用模型获得完全相同的命名。发布副本移除了逐条翻译常量，生成的私有人工复核表译文留空，不改变主题映射及统计代码。若聚类结果改变，不能盲用旧簇 ID 映射。

本次验证范围：所有发布 Python 源码语法、Dashboard 聚合重建哈希一致、隔离副本 npm ci/build。没有重跑全量 SQL/Python/Embedding；全量分析复现仍需原始数据、模型与环境核验。

本目录 outputs 中仅分发审核过的聚合输出和最小元数据。执行分析会生成不适合公开的行级数据；.gitignore 默认忽略新增分析 outputs/data/docs，不能把运行后的目录整体上传。
