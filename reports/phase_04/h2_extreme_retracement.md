# H2 — Prior Boundary + Retracement

Conclusion: **inconclusive**

```json
{
  "conclusion": "inconclusive",
  "joint_sequence": {
    "conclusion": "inconclusive",
    "windows_ms": [
      1000,
      2000,
      5000
    ],
    "results": [
      {
        "split": "development",
        "window_ms": 1000,
        "summary": {
          "pairs": 188,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.4,
          "paired_mean_difference": 0.01888297872340425,
          "matched_separation_rate": 0.3882978723404255,
          "cluster_bootstrap_ci95": [
            -0.05345744680851064,
            0.09282579787234034
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 2000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.4,
          "paired_mean_difference": 0.11308900523560209,
          "matched_separation_rate": 0.518324607329843,
          "cluster_bootstrap_ci95": [
            0.040811518324607325,
            0.19060209424083732
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 5000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.6,
          "paired_mean_difference": 0.031413612565445025,
          "matched_separation_rate": 0.5235602094240838,
          "cluster_bootstrap_ci95": [
            -0.04607329842931938,
            0.1099476439790576
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 1000,
        "summary": {
          "pairs": 201,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.4,
          "paired_mean_difference": 0.03051409618573799,
          "matched_separation_rate": 0.39800995024875624,
          "cluster_bootstrap_ci95": [
            -0.04742951907131011,
            0.10871061359867325
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 2000,
        "summary": {
          "pairs": 206,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.4,
          "paired_mean_difference": 0.030339805825242733,
          "matched_separation_rate": 0.42718446601941745,
          "cluster_bootstrap_ci95": [
            -0.04320388349514563,
            0.10485436893203882
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 5000,
        "summary": {
          "pairs": 207,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.4,
          "paired_mean_difference": 0.020289855072463756,
          "matched_separation_rate": 0.4782608695652174,
          "cluster_bootstrap_ci95": [
            -0.052173913043478265,
            0.09565217391304347
          ]
        }
      }
    ]
  },
  "touch_component": {
    "conclusion": "supported",
    "windows_ms": [
      1000,
      2000,
      5000
    ],
    "results": [
      {
        "split": "development",
        "window_ms": 1000,
        "summary": {
          "pairs": 188,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.6,
          "paired_mean_difference": 0.049999999999999996,
          "matched_separation_rate": 0.5478723404255319,
          "cluster_bootstrap_ci95": [
            -0.02740026595744681,
            0.12739361702127658
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 2000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.6,
          "paired_mean_difference": 0.15811518324607327,
          "matched_separation_rate": 0.6544502617801047,
          "cluster_bootstrap_ci95": [
            0.08586387434554973,
            0.23141361256544501
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 5000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.6,
          "paired_mean_difference": 0.07748691099476439,
          "matched_separation_rate": 0.6020942408376964,
          "cluster_bootstrap_ci95": [
            0.0031151832460732964,
            0.1518324607329843
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 1000,
        "summary": {
          "pairs": 201,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.4,
          "paired_mean_difference": 0.07064676616915422,
          "matched_separation_rate": 0.5323383084577115,
          "cluster_bootstrap_ci95": [
            -0.009465174129353226,
            0.15075248756218895
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 2000,
        "summary": {
          "pairs": 206,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.4,
          "paired_mean_difference": 0.08932038834951456,
          "matched_separation_rate": 0.558252427184466,
          "cluster_bootstrap_ci95": [
            0.017949029126213583,
            0.16262135922330093
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 5000,
        "summary": {
          "pairs": 207,
          "bootstrap_draws": 5000,
          "positive_median": 1.0,
          "control_median": 0.6,
          "paired_mean_difference": 0.08888888888888888,
          "matched_separation_rate": 0.5797101449275363,
          "cluster_bootstrap_ci95": [
            0.016425120772946868,
            0.1623188405797101
          ]
        }
      }
    ]
  },
  "retracement_component": {
    "conclusion": "inconclusive",
    "windows_ms": [
      1000,
      2000,
      5000
    ],
    "results": [
      {
        "split": "development",
        "window_ms": 1000,
        "summary": {
          "pairs": 188,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.20817169653062062,
          "paired_mean_difference": 0.45901710922206523,
          "matched_separation_rate": 0.2712765957446808,
          "cluster_bootstrap_ci95": [
            -0.013122495203824787,
            1.090914734931207
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 2000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 0.04477611940124267,
          "control_median": 0.17851851851905998,
          "paired_mean_difference": 0.06932809152256285,
          "matched_separation_rate": 0.387434554973822,
          "cluster_bootstrap_ci95": [
            -0.04263507867057055,
            0.18286302054158413
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 5000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 0.027777777778479548,
          "control_median": 0.19166666666575086,
          "paired_mean_difference": -0.0012395731437981011,
          "matched_separation_rate": 0.32460732984293195,
          "cluster_bootstrap_ci95": [
            -0.08397499896123777,
            0.08859589134543529
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 1000,
        "summary": {
          "pairs": 201,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.18736141906921108,
          "paired_mean_difference": 0.2257905974327219,
          "matched_separation_rate": 0.27860696517412936,
          "cluster_bootstrap_ci95": [
            -0.14956533342869513,
            0.7531693778982261
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 2000,
        "summary": {
          "pairs": 206,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.2231452455601195,
          "paired_mean_difference": 0.0500050801225551,
          "matched_separation_rate": 0.3155339805825243,
          "cluster_bootstrap_ci95": [
            -0.1235460700467101,
            0.2236999479559886
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 5000,
        "summary": {
          "pairs": 207,
          "bootstrap_draws": 5000,
          "positive_median": 0.0,
          "control_median": 0.1867084639504829,
          "paired_mean_difference": 0.016827678488830974,
          "matched_separation_rate": 0.3333333333333333,
          "cluster_bootstrap_ci95": [
            -0.1255870347515626,
            0.15129183933034654
          ]
        }
      }
    ]
  },
  "definition": "For each pre-registered sequence window w, the prior boundary is computed on [t-2w, t-w). The sequence window is [t-w, t]. A valid sequence touches or breaks the side-appropriate prior boundary before t and then retraces/bounces before t."
}
```
