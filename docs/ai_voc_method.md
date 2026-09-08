# AI Voice of Customer

Portuguese review body → normalization and unique-text embedding → semantic clustering → AI-assisted taxonomy → structured order-level validation. 40,748 canonical written reviews; 35,519 unique embedded texts. Primary corpus score<=3: 14,375; positive supplement score>=4: 26,373. Not all reviews are core-window reviews.

Multilingual MiniLM, sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2, 384 dimensions, ONNX uint8 CPU, attention-mask mean pooling and L2 normalization, max 128 tokens. Original Portuguese is embedded directly. Accepted run did not use TF-IDF fallback. Revision e8f8c211226b894fcb81acc59f3b34ba3efd5f42. No model weights distributed.

Primary K=8, seed=42; multiple seed stability and structured validation are diagnostics, not classification accuracy. Cluster labels merge into six primary themes plus three positive themes. Mixed / Other 62.70% conservatively includes broad product-condition mixture. The deterministic token audit confirms 1 of 35,519 unique texts exceeds 128 tokens; the maximum length is 186 tokens. The manifest retains the audit clarification; actual embeddings used 128 throughout.

No human Gold Set. The original centroid/random examples supported AI-assisted naming, not an unbiased accuracy estimate. Per-review examples and translations are excluded. Frozen taxonomy code replays cluster decisions; it does not provide a supervised classifier. Accuracy, Precision, Recall and F1 are not reported.

Hero: waiting-related late rate 56.18% in all core written samples; 7.40% in after-delivery-answer written samples; 2.22% in the latter full written baseline. After-delivery is based on review_answer_timestamp, not review_creation_date. Timing and selection change interpretation; the differences are not intervention results.
