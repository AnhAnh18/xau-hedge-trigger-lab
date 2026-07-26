# H1 — Rolling Boundary

Conclusion: **supported**

```json
[
  {
    "split": "development",
    "window_ms": 500,
    "summary": {
      "pairs": 334,
      "positive_median": 0.4615384615376543,
      "control_median": 0.5050235478808021,
      "paired_mean_difference": -0.025327339729360326,
      "matched_separation_rate": 0.46706586826347307,
      "cluster_bootstrap_ci95": [
        -0.0737075905876079,
        0.023450107807957265
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 1000,
    "summary": {
      "pairs": 338,
      "positive_median": 0.5405844155901436,
      "control_median": 0.5238387122906957,
      "paired_mean_difference": -0.008019747820487014,
      "matched_separation_rate": 0.5088757396449705,
      "cluster_bootstrap_ci95": [
        -0.05825991801776759,
        0.03630242540738689
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 2000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.6814159292033118,
      "control_median": 0.5394014163041763,
      "paired_mean_difference": 0.020090994277144936,
      "matched_separation_rate": 0.5693215339233039,
      "cluster_bootstrap_ci95": [
        -0.02892977826030854,
        0.06302932204091612
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 5000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.7673267326727413,
      "control_median": 0.5797013552485037,
      "paired_mean_difference": 0.0790124263444533,
      "matched_separation_rate": 0.640117994100295,
      "cluster_bootstrap_ci95": [
        0.04029857309331005,
        0.1199566698466109
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 10000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.8267326732680066,
      "control_median": 0.6260920743001004,
      "paired_mean_difference": 0.0868975338041777,
      "matched_separation_rate": 0.6607669616519174,
      "cluster_bootstrap_ci95": [
        0.04721492904581218,
        0.12134702218639838
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 30000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.7980997624702241,
      "control_median": 0.6395740656094013,
      "paired_mean_difference": 0.07731017461044708,
      "matched_separation_rate": 0.6460176991150443,
      "cluster_bootstrap_ci95": [
        0.04597478296204632,
        0.11206932881362706
      ]
    }
  },
  {
    "split": "development",
    "window_ms": 60000,
    "summary": {
      "pairs": 339,
      "positive_median": 0.8040201005027836,
      "control_median": 0.6313692134629585,
      "paired_mean_difference": 0.08073627016697267,
      "matched_separation_rate": 0.6460176991150443,
      "cluster_bootstrap_ci95": [
        0.04637046459956126,
        0.11062931081981511
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 500,
    "summary": {
      "pairs": 289,
      "positive_median": 0.5,
      "control_median": 0.5005291005295807,
      "paired_mean_difference": 0.000992539408471903,
      "matched_separation_rate": 0.5017301038062284,
      "cluster_bootstrap_ci95": [
        -0.059094208466773726,
        0.06485061742573983
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 1000,
    "summary": {
      "pairs": 291,
      "positive_median": 0.5789473684225642,
      "control_median": 0.49417582417987793,
      "paired_mean_difference": 0.022361980345240784,
      "matched_separation_rate": 0.5360824742268041,
      "cluster_bootstrap_ci95": [
        -0.02111812328796682,
        0.07455469305938733
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 2000,
    "summary": {
      "pairs": 293,
      "positive_median": 0.6263736263750321,
      "control_median": 0.5071420083184304,
      "paired_mean_difference": 0.05029263430396115,
      "matched_separation_rate": 0.5631399317406144,
      "cluster_bootstrap_ci95": [
        0.002818420939045191,
        0.09467513986699928
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 5000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.7461340206186384,
      "control_median": 0.5253587549925919,
      "paired_mean_difference": 0.09563364378238262,
      "matched_separation_rate": 0.6258503401360545,
      "cluster_bootstrap_ci95": [
        0.04752307273206167,
        0.13665039985102323
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 10000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.7740699542706235,
      "control_median": 0.5513363110985069,
      "paired_mean_difference": 0.08262065813479963,
      "matched_separation_rate": 0.6292517006802721,
      "cluster_bootstrap_ci95": [
        0.040091427815269774,
        0.12814253272804055
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 30000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.7688336457203457,
      "control_median": 0.5849601302705354,
      "paired_mean_difference": 0.085757101141037,
      "matched_separation_rate": 0.6258503401360545,
      "cluster_bootstrap_ci95": [
        0.044649450634040015,
        0.12902504590325847
      ]
    }
  },
  {
    "split": "holdout",
    "window_ms": 60000,
    "summary": {
      "pairs": 294,
      "positive_median": 0.7607645814897996,
      "control_median": 0.6041748322216483,
      "paired_mean_difference": 0.07175863510102853,
      "matched_separation_rate": 0.5850340136054422,
      "cluster_bootstrap_ci95": [
        0.03552766906772737,
        0.11496210363856155
      ]
    }
  }
]
```
