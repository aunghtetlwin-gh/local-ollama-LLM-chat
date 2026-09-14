# Statistical Benchmark Summary

Mean, minimum, maximum, and sample standard deviation are reported below.

## Controlled Performance

| Model | State | Mean Latency (s) | Min | Max | Std Dev | Mean Load (s) | Mean Generation (tok/s) |
|---|---|---:|---:|---:|---:|---:|---:|
| qwen3:1.7b | cold | 2.307 | 2.233 | 2.42 | 0.1 | 1.399 | 246.153 |
| qwen3:1.7b | warm | 0.783 | 0.768 | 0.792 | 0.013 | 0.001 | 267.34 |
| qwen3:8b | cold | 6.055 | 6.013 | 6.112 | 0.051 | 1.844 | 76.353 |
| qwen3:8b | warm | 3.403 | 3.395 | 3.418 | 0.013 | 0.002 | 78.787 |
| gemma4:12b | cold | 18.11 | 18.078 | 18.172 | 0.054 | 2.879 | 49.637 |
| gemma4:12b | warm | 16.577 | 16.478 | 16.68 | 0.101 | 0.002 | 49.797 |

## Sustained GPU Resource Use

| Model | Mean GPU (%) | GPU Std Dev | Mean VRAM (MiB) | Mean Power (W) | Max Observed Temp (C) | Mean Generation (tok/s) |
|---|---:|---:|---:|---:|---:|---:|
| qwen3:1.7b | 89.207 | 6.158 | 1911.0 | 122.273 | 58.0 | 257.377 |
| qwen3:8b | 93.99 | 3.561 | 5607.0 | 155.903 | 64.0 | 77.31 |
| gemma4:12b | 93.803 | 0.576 | 8323.0 | 158.12 | 64.0 | 49.29 |

## Multi-Prompt Cross-Task Summary

> These statistics summarize variation across five different task categories. They should not be interpreted as repeated trials of the same workload.

| Model | Mean Latency (s) | Min | Max | Std Dev | Mean Eval Tokens | Mean Generation (tok/s) |
|---|---:|---:|---:|---:|---:|---:|
| qwen3:1.7b | 3.1 | 1.167 | 5.797 | 1.904 | 756.4 | 250.998 |
| qwen3:8b | 8.155 | 2.786 | 15.939 | 5.533 | 621.4 | 77.35 |
| gemma4:12b | 27.643 | 5.288 | 51.018 | 16.233 | 1339.2 | 49.072 |
