# Data sources and attribution

Data provider: Olist. Source datasets:

- [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), accepted snapshot metadata version 2.
- [Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist), accepted snapshot version 2.

Both accepted official source metadata records identify **CC BY-NC-SA 4.0**. Both official dataset pages were rechecked and confirmed as CC BY-NC-SA 4.0 in the Session 6.1 human verification supplied for this release. [License deed](https://creativecommons.org/licenses/by-nc-sa/4.0/) and [legal code](https://creativecommons.org/licenses/by-nc-sa/4.0/legalcode) describe attribution, noncommercial and share-alike conditions.

No raw dataset is redistributed. dashboard/data and analysis/outputs contain filtered aggregate derivatives plus minimal metadata. Transformations: deterministic deduplication/canonical selection, order-grain aggregation, core/maturity filters, descriptive statistics, semantic clustering and aggregate validation. Report charts and dashboard previews derive from those aggregates. Retain Olist attribution, source links, license notice and transformation disclosure when sharing these derivatives; do not relabel the data derivatives as MIT. This portfolio project is not a legal guarantee about every possible downstream use.

Model source: [Multilingual MiniLM model card](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2). Only source code and run metadata are included; no weights, tokenizer corpus or individual review examples are distributed. Third-party package licenses remain separate.
