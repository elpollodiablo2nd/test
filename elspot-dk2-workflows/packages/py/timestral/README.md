# timestral (vendored)

Vendored copy of the standalone Timestral inference package from
[github.com/mistralai/timestral](https://github.com/mistralai/timestral) at commit
`a534bdbd244d64f3d9d743f46c7bf6fc330ed4ff`, licensed **Apache-2.0** (see `LICENSE`).

Vendored (instead of a `git+https` dependency) so the managed-deployment Docker build does not
need a Git executable in the build image. The model weights are not vendored; they download at
runtime from the Hugging Face Hub (`mistralai/Timestral-<size>`, Modified MIT license) into
`HF_CACHE_DIR`.

Upstream usage:

```python
from timestral import TimestralForecaster
forecaster = TimestralForecaster.from_pretrained("mistralai/Timestral-28M")  # device="cpu"
forecast = forecaster.forecast(context, prediction_length=96)  # context: (B, V, T), NaN = missing
forecast.median          # (B, V, 96)
forecast.quantile(0.9)   # (B, V, 96); 21 quantile levels 0.01..0.99
```
