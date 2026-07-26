# H2 — Extreme + Retracement

Conclusion: **rejected**

```json
[
  {
    "split": "development",
    "window_ms": 500,
    "summary": {
      "pairs": 334,
      "positive_median": 0.5384615384623457,
      "control_median": 0.49497645211919794,
      "paired_mean_difference": 0.025327339729360337,
      "matched_separation_rate": 0.5329341317365269,
      "cluster_bootstrap_ci95": [
        -0.02345010780795731,
        0.07370759058760787
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 1000,
    "summary": {
      "pairs": 338,
      "positive_median": 0.4594155844098564,
      "control_median": 0.4761612877093043,
      "paired_mean_difference": 0.008019747820487009,
      "matched_separation_rate": 0.4911242603550296,
      "cluster_bootstrap_ci95": [
        -0.03630242540738694,
        0.05825991801776759
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 2000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.3185840707966881,
      "control_median": 0.4605985836958237,
      "paired_mean_difference": -0.020090994277144926,
      "matched_separation_rate": 0.4306784660766962,
      "cluster_bootstrap_ci95": [
        -0.06302932204091612,
        0.02892977826030852
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 5000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.2326732673272587,
      "control_median": 0.4202986447514963,
      "paired_mean_difference": -0.0790124263444533,
      "matched_separation_rate": 0.35988200589970504,
      "cluster_bootstrap_ci95": [
        -0.1199566698466109,
        -0.04029857309331006
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 10000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.17326732673199344,
      "control_median": 0.37390792569989956,
      "paired_mean_difference": -0.0868975338041777,
      "matched_separation_rate": 0.3392330383480826,
      "cluster_bootstrap_ci95": [
        -0.12134702218639835,
        -0.04721492904581222
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 30000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.20190023752977587,
      "control_median": 0.3604259343905987,
      "paired_mean_difference": -0.07731017461044709,
      "matched_separation_rate": 0.35398230088495575,
      "cluster_bootstrap_ci95": [
        -0.11206932881362705,
        -0.04597478296204632
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 60000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.19597989949721642,
      "control_median": 0.36863078653704145,
      "paired_mean_difference": -0.08073627016697267,
      "matched_separation_rate": 0.35398230088495575,
      "cluster_bootstrap_ci95": [
        -0.11062931081981511,
        -0.04637046459956127
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 500,
    "summary": {
      "pairs": 289,
      "positive_median": 0.5,
      "control_median": 0.4994708994704193,
      "paired_mean_difference": -0.0009925394084719062,
      "matched_separation_rate": 0.49480968858131485,
      "cluster_bootstrap_ci95": [
        -0.06485061742573986,
        0.05909420846677371
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 1000,
    "summary": {
      "pairs": 291,
      "positive_median": 0.4210526315774357,
      "control_median": 0.5058241758201221,
      "paired_mean_difference": -0.022361980345240784,
      "matched_separation_rate": 0.4639175257731959,
      "cluster_bootstrap_ci95": [
        -0.07455469305938738,
        0.021118123287966816
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 2000,
    "summary": {
      "pairs": 293,
      "positive_median": 0.3736263736249678,
      "control_median": 0.49285799168156963,
      "paired_mean_difference": -0.050292634303961144,
      "matched_separation_rate": 0.43686006825938567,
      "cluster_bootstrap_ci95": [
        -0.0946751398669993,
        -0.002818420939045229
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 5000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.2538659793813615,
      "control_median": 0.4746412450074081,
      "paired_mean_difference": -0.09563364378238262,
      "matched_separation_rate": 0.3741496598639456,
      "cluster_bootstrap_ci95": [
        -0.13665039985102323,
        -0.047523072732061675
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 10000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.2259300457293764,
      "control_median": 0.4486636889014931,
      "paired_mean_difference": -0.08262065813479963,
      "matched_separation_rate": 0.3707482993197279,
      "cluster_bootstrap_ci95": [
        -0.12814253272804058,
        -0.04009142781526981
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 30000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.23116635427965432,
      "control_median": 0.41503986972946466,
      "paired_mean_difference": -0.085757101141037,
      "matched_separation_rate": 0.3741496598639456,
      "cluster_bootstrap_ci95": [
        -0.12902504590325847,
        -0.04464945063404002
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 60000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.2392354185102003,
      "control_median": 0.39582516777835186,
      "paired_mean_difference": -0.07175863510102853,
      "matched_separation_rate": 0.41496598639455784,
      "cluster_bootstrap_ci95": [
        -0.11496210363856157,
        -0.03552766906772738
      ]
    }
  }
]
```
