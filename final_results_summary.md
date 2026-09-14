# Final Model Comparison

| Model | Warm Latency (s) | Generation (tok/s) | VRAM (GiB) | GPU Util (%) | Power (W) | Max Temp (C) | Quality (/5) | Objective |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3 1.7B | 0.783 | 257.38 | 1.87 | 89.21 | 122.27 | 58.0 | 4.6 | 4/5 |
| Qwen3 8B | 3.403 | 77.31 | 5.48 | 93.99 | 155.9 | 64.0 | 4.96 | 5/5 |
| Gemma4 12B | 16.577 | 49.29 | 8.13 | 93.8 | 158.12 | 64.0 | 4.88 | 4/5 |

## Interpretation

- **Qwen3 1.7B:** lowest resource usage and highest generation throughput, but lower overall quality than the larger models in this benchmark.
- **Qwen3 8B:** strongest overall quality result while retaining substantially lower latency and VRAM use than Gemma4 12B.
- **Gemma4 12B:** strong response quality but highest VRAM requirement and slowest generation speed.

These results demonstrate a trade-off between inference performance, hardware resource consumption, and response quality.
