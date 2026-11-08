# V2 本地真实模型评测

评测日期：2026-11-04

执行命令：

```powershell
python scripts/run_acceptance_matrix.py --production-only --timeout 1800
```

## 环境

- LLM：Ollama `qwen2.5:1.5b`
- Embedding：`BAAI/bge-small-zh-v1.5`，CPU，本地缓存离线加载
- 检索：`hybrid`
- 记忆：`M3`（治理模式）
- 技能：`reviewed`
- 数据集：`aftersales-smoke-v1`，50 条，SHA-256 `ee4b98fdf3e4bc5a03446feefd96e5bf4a5a6429fc7f5303f6cca426dfabb177`

## 结果

| 指标 | 结果 |
| --- | ---: |
| 任务成功率 | 1.0000 |
| 决策准确率 | 1.0000 |
| 引用精度 | 0.9250 |
| Recall@K | 0.7692 |
| MRR / NDCG@K | 0.7692 / 0.7692 |
| 工具准确率 | 1.0000 |
| 危险动作率 | 0.0000 |
| P95 | 3979.43 ms |
| Badcase | 0 |

原始运行 ID：`72690f0e-ddf4-4edc-b41c-f91e458a43e8`。本轮同时验证了本地模型缓存的离线加载；`MODEL_OFFLINE=true` 可避免已下载 BGE 权重仍访问 Hugging Face 元数据接口。

LightRAG 与 OpenViking 未计入本轮，因为没有外部服务地址；二者仍是非生产研究对照组，不影响默认 hybrid 验收。
