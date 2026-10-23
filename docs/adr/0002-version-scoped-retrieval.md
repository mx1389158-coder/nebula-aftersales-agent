# ADR-0002：版本过滤必须先于相似度排序

状态：已接受

检索先强制过滤 `tenant_id`、`product_id`、`model` 和 `firmware_version`，再执行 BM25、稠密向量、RRF 与 MMR。通用文档允许 `model` 或 `firmware_version` 为空，但不同明确版本之间禁止互相召回。

这样可以避免高语义相似度的旧版说明覆盖当前版本。相关行为由 `test_retrieval_never_crosses_firmware_version` 固化。

