# H3 — Unlock Momentum

Conclusion: **supported**

```json
{
  "conclusion": "supported",
  "windows_ms": [
    500,
    1000,
    2000
  ],
  "results": [
    {
      "split": "development",
      "window_ms": 500,
      "summary": {
        "pairs": 324,
        "bootstrap_draws": 5000,
        "positive_median": 3.6742042269777286e-06,
        "control_median": 2.560720909317027e-07,
        "paired_mean_difference": 5.784211384160927e-06,
        "matched_separation_rate": 0.5617283950617284,
        "cluster_bootstrap_ci95": [
          1.0938509154134763e-06,
          1.0452205952905591e-05
        ]
      }
    },
    {
      "split": "development",
      "window_ms": 1000,
      "summary": {
        "pairs": 325,
        "bootstrap_draws": 5000,
        "positive_median": 6.161057434561634e-06,
        "control_median": -4.6601048417915793e-07,
        "paired_mean_difference": 5.780381484740155e-06,
        "matched_separation_rate": 0.563076923076923,
        "cluster_bootstrap_ci95": [
          -1.0662782307146325e-06,
          1.2423737968078427e-05
        ]
      }
    },
    {
      "split": "development",
      "window_ms": 2000,
      "summary": {
        "pairs": 325,
        "bootstrap_draws": 5000,
        "positive_median": 1.2356021459325461e-06,
        "control_median": 1.2204740321264396e-06,
        "paired_mean_difference": 1.6984270166351069e-06,
        "matched_separation_rate": 0.48615384615384616,
        "cluster_bootstrap_ci95": [
          -7.91231318543618e-06,
          1.2394244896771763e-05
        ]
      }
    },
    {
      "split": "holdout",
      "window_ms": 500,
      "summary": {
        "pairs": 289,
        "bootstrap_draws": 5000,
        "positive_median": 6.1313356625181115e-06,
        "control_median": -4.90486419457703e-07,
        "paired_mean_difference": 1.1989301640607491e-05,
        "matched_separation_rate": 0.6055363321799307,
        "cluster_bootstrap_ci95": [
          7.236890001318381e-06,
          1.6823396309878006e-05
        ]
      }
    },
    {
      "split": "holdout",
      "window_ms": 1000,
      "summary": {
        "pairs": 289,
        "bootstrap_draws": 5000,
        "positive_median": 7.375456202662889e-06,
        "control_median": -2.5290940375288784e-07,
        "paired_mean_difference": 1.5312611088513855e-05,
        "matched_separation_rate": 0.5986159169550173,
        "cluster_bootstrap_ci95": [
          9.232834575266089e-06,
          2.1173544424313532e-05
        ]
      }
    },
    {
      "split": "holdout",
      "window_ms": 2000,
      "summary": {
        "pairs": 289,
        "bootstrap_draws": 5000,
        "positive_median": 1.108728030252415e-05,
        "control_median": -4.935123244509398e-07,
        "paired_mean_difference": 1.8171291045756014e-05,
        "matched_separation_rate": 0.6262975778546713,
        "cluster_bootstrap_ci95": [
          9.057758208598824e-06,
          2.7214290808487077e-05
        ]
      }
    }
  ],
  "median_mid": 4052.3199999999997,
  "median_spread": 0.22999999999956344,
  "holdout_price_unit_effects": [
    {
      "window_ms": 500,
      "paired_effect_price_units": 0.04858448682426655,
      "effect_as_fraction_of_median_spread": 0.21123689923634245
    },
    {
      "window_ms": 1000,
      "paired_effect_price_units": 0.062051600166206464,
      "effect_as_fraction_of_median_spread": 0.2697895659405402
    },
    {
      "window_ms": 2000,
      "paired_effect_price_units": 0.07363588613053801,
      "effect_as_fraction_of_median_spread": 0.3201560266551208
    }
  ],
  "interpretation": "The signed-momentum association is timing-sensitive. Its price-unit effect is smaller than the median spread and is not a standalone tradeable edge."
}
```
