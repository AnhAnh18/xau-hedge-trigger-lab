# H1 — Rolling Boundary

Conclusion: **confounded/inconclusive**

```json
{
  "conclusion": "confounded/inconclusive",
  "primary_control_supported": {
    "conclusion": "inconclusive",
    "windows_ms": [
      2000,
      5000,
      10000,
      30000,
      60000
    ],
    "results": [
      {
        "split": "development",
        "window_ms": 2000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 0.5217391304392527,
          "control_median": 0.5163742690061859,
          "paired_mean_difference": -0.00625085736102588,
          "matched_separation_rate": 0.5287958115183246,
          "cluster_bootstrap_ci95": [
            -0.06905653776298716,
            0.053624641449246516
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 5000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 0.6034482758612039,
          "control_median": 0.5438551184692698,
          "paired_mean_difference": 0.020412509097691354,
          "matched_separation_rate": 0.5392670157068062,
          "cluster_bootstrap_ci95": [
            -0.03516455394488602,
            0.07673529729711218
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 10000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 0.7662337662335208,
          "control_median": 0.5966103320234486,
          "paired_mean_difference": 0.034538590664585415,
          "matched_separation_rate": 0.5759162303664922,
          "cluster_bootstrap_ci95": [
            -0.01963671702482135,
            0.0857509589312875
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 30000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 0.7708978328173741,
          "control_median": 0.636846191865123,
          "paired_mean_difference": 0.04245726300069547,
          "matched_separation_rate": 0.612565445026178,
          "cluster_bootstrap_ci95": [
            -0.0065682067853849125,
            0.08895014704943728
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 60000,
        "summary": {
          "pairs": 191,
          "bootstrap_draws": 5000,
          "positive_median": 0.7958115183245791,
          "control_median": 0.6341353258710072,
          "paired_mean_difference": 0.04635439663476753,
          "matched_separation_rate": 0.6178010471204188,
          "cluster_bootstrap_ci95": [
            -0.0003551736730462188,
            0.09297565842934238
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 2000,
        "summary": {
          "pairs": 206,
          "bootstrap_draws": 5000,
          "positive_median": 0.4761904761910433,
          "control_median": 0.5018090766011273,
          "paired_mean_difference": 0.0011966620325590256,
          "matched_separation_rate": 0.49514563106796117,
          "cluster_bootstrap_ci95": [
            -0.06064272765442539,
            0.0619476075779345
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 5000,
        "summary": {
          "pairs": 207,
          "bootstrap_draws": 5000,
          "positive_median": 0.5581395348828355,
          "control_median": 0.5248635318151178,
          "paired_mean_difference": 0.029359172022355055,
          "matched_separation_rate": 0.5458937198067633,
          "cluster_bootstrap_ci95": [
            -0.026495772260698047,
            0.08558459197617406
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 10000,
        "summary": {
          "pairs": 207,
          "bootstrap_draws": 5000,
          "positive_median": 0.6000000000012127,
          "control_median": 0.5492947970434993,
          "paired_mean_difference": 0.013835760375002924,
          "matched_separation_rate": 0.5458937198067633,
          "cluster_bootstrap_ci95": [
            -0.04277961576824913,
            0.06691774500720543
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 30000,
        "summary": {
          "pairs": 207,
          "bootstrap_draws": 5000,
          "positive_median": 0.6796116504857113,
          "control_median": 0.5785999701462868,
          "paired_mean_difference": 0.03466564548235547,
          "matched_separation_rate": 0.5652173913043478,
          "cluster_bootstrap_ci95": [
            -0.015522916555509931,
            0.08401900598072579
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 60000,
        "summary": {
          "pairs": 207,
          "bootstrap_draws": 5000,
          "positive_median": 0.6751592356687788,
          "control_median": 0.5996969071492919,
          "paired_mean_difference": 0.022769075006837867,
          "matched_separation_rate": 0.5314009661835749,
          "cluster_bootstrap_ci95": [
            -0.02542818441005573,
            0.07160071413107506
          ]
        }
      }
    ]
  },
  "descriptive_all_positive": {
    "conclusion": "supported",
    "windows_ms": [
      2000,
      5000,
      10000,
      30000,
      60000
    ],
    "results": [
      {
        "split": "development",
        "window_ms": 2000,
        "summary": {
          "pairs": 339,
          "bootstrap_draws": 5000,
          "positive_median": 0.6814159292033118,
          "control_median": 0.5394014163041763,
          "paired_mean_difference": 0.020090994277144936,
          "matched_separation_rate": 0.5693215339233039,
          "cluster_bootstrap_ci95": [
            -0.026869556159529295,
            0.0640879194896016
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 5000,
        "summary": {
          "pairs": 339,
          "bootstrap_draws": 5000,
          "positive_median": 0.7673267326727413,
          "control_median": 0.5797013552485037,
          "paired_mean_difference": 0.0790124263444533,
          "matched_separation_rate": 0.640117994100295,
          "cluster_bootstrap_ci95": [
            0.03910761606586456,
            0.11836004757028891
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 10000,
        "summary": {
          "pairs": 339,
          "bootstrap_draws": 5000,
          "positive_median": 0.8267326732680066,
          "control_median": 0.6260920743001004,
          "paired_mean_difference": 0.0868975338041777,
          "matched_separation_rate": 0.6607669616519174,
          "cluster_bootstrap_ci95": [
            0.04902197511705343,
            0.12374545329878248
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 30000,
        "summary": {
          "pairs": 339,
          "bootstrap_draws": 5000,
          "positive_median": 0.7980997624702241,
          "control_median": 0.6395740656094013,
          "paired_mean_difference": 0.07731017461044708,
          "matched_separation_rate": 0.6460176991150443,
          "cluster_bootstrap_ci95": [
            0.04398694740891111,
            0.11057947942432025
          ]
        }
      },
      {
        "split": "development",
        "window_ms": 60000,
        "summary": {
          "pairs": 339,
          "bootstrap_draws": 5000,
          "positive_median": 0.8040201005027836,
          "control_median": 0.6313692134629585,
          "paired_mean_difference": 0.08073627016697267,
          "matched_separation_rate": 0.6460176991150443,
          "cluster_bootstrap_ci95": [
            0.046327563921135004,
            0.11387091583631172
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 2000,
        "summary": {
          "pairs": 293,
          "bootstrap_draws": 5000,
          "positive_median": 0.6263736263750321,
          "control_median": 0.5071420083184304,
          "paired_mean_difference": 0.05029263430396115,
          "matched_separation_rate": 0.5631399317406144,
          "cluster_bootstrap_ci95": [
            0.0016161798850513553,
            0.09764161224029441
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 5000,
        "summary": {
          "pairs": 294,
          "bootstrap_draws": 5000,
          "positive_median": 0.7461340206186384,
          "control_median": 0.5253587549925919,
          "paired_mean_difference": 0.09563364378238262,
          "matched_separation_rate": 0.6258503401360545,
          "cluster_bootstrap_ci95": [
            0.048861253379357705,
            0.1416594834030162
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 10000,
        "summary": {
          "pairs": 294,
          "bootstrap_draws": 5000,
          "positive_median": 0.7740699542706235,
          "control_median": 0.5513363110985069,
          "paired_mean_difference": 0.08262065813479963,
          "matched_separation_rate": 0.6292517006802721,
          "cluster_bootstrap_ci95": [
            0.039144275860427444,
            0.12623006114098795
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 30000,
        "summary": {
          "pairs": 294,
          "bootstrap_draws": 5000,
          "positive_median": 0.7688336457203457,
          "control_median": 0.5849601302705354,
          "paired_mean_difference": 0.085757101141037,
          "matched_separation_rate": 0.6258503401360545,
          "cluster_bootstrap_ci95": [
            0.043943054516131626,
            0.12551381104949777
          ]
        }
      },
      {
        "split": "holdout",
        "window_ms": 60000,
        "summary": {
          "pairs": 294,
          "bootstrap_draws": 5000,
          "positive_median": 0.7607645814897996,
          "control_median": 0.6041748322216483,
          "paired_mean_difference": 0.07175863510102853,
          "matched_separation_rate": 0.5850340136054422,
          "cluster_bootstrap_ci95": [
            0.03236048918435884,
            0.11103751291402449
          ]
        }
      }
    ]
  },
  "state_age_strata": {
    "0-6s": {
      "positive_count": 237,
      "control_supported_positive_count": 0,
      "analysis": {
        "conclusion": "supported",
        "windows_ms": [
          2000,
          5000,
          10000,
          30000,
          60000
        ],
        "results": [
          {
            "split": "development",
            "window_ms": 2000,
            "summary": {
              "pairs": 148,
              "bootstrap_draws": 5000,
              "positive_median": 0.7953612479454825,
              "control_median": 0.5650236594324518,
              "paired_mean_difference": 0.05408622172910861,
              "matched_separation_rate": 0.6216216216216216,
              "cluster_bootstrap_ci95": [
                -0.014063030890161188,
                0.12022180525211461
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 5000,
            "summary": {
              "pairs": 148,
              "bootstrap_draws": 5000,
              "positive_median": 0.8852482545324414,
              "control_median": 0.5992491558980279,
              "paired_mean_difference": 0.15463799522372038,
              "matched_separation_rate": 0.7702702702702703,
              "cluster_bootstrap_ci95": [
                0.0993809520492894,
                0.20746227669944345
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 10000,
            "summary": {
              "pairs": 148,
              "bootstrap_draws": 5000,
              "positive_median": 0.8998567677248663,
              "control_median": 0.6625526383637885,
              "paired_mean_difference": 0.1544688725856786,
              "matched_separation_rate": 0.7702702702702703,
              "cluster_bootstrap_ci95": [
                0.10709109886031562,
                0.20131903414992752
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 30000,
            "summary": {
              "pairs": 148,
              "bootstrap_draws": 5000,
              "positive_median": 0.8619883835467568,
              "control_median": 0.6402795310817938,
              "paired_mean_difference": 0.12228926999870762,
              "matched_separation_rate": 0.6891891891891891,
              "cluster_bootstrap_ci95": [
                0.07612144101054727,
                0.1660493560182007
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 60000,
            "summary": {
              "pairs": 148,
              "bootstrap_draws": 5000,
              "positive_median": 0.820215129107321,
              "control_median": 0.6231792244022178,
              "paired_mean_difference": 0.12510747182002122,
              "matched_separation_rate": 0.6824324324324325,
              "cluster_bootstrap_ci95": [
                0.07479804327243054,
                0.17513753012465413
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 2000,
            "summary": {
              "pairs": 87,
              "bootstrap_draws": 5000,
              "positive_median": 0.8479452054793761,
              "control_median": 0.5137194998979923,
              "paired_mean_difference": 0.16654286749831557,
              "matched_separation_rate": 0.7241379310344828,
              "cluster_bootstrap_ci95": [
                0.09280977185083283,
                0.2358040728432527
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 5000,
            "summary": {
              "pairs": 87,
              "bootstrap_draws": 5000,
              "positive_median": 0.9058823529407674,
              "control_median": 0.5359181225074572,
              "paired_mean_difference": 0.25332118003899984,
              "matched_separation_rate": 0.8160919540229885,
              "cluster_bootstrap_ci95": [
                0.1842112277169966,
                0.31815554176729594
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 10000,
            "summary": {
              "pairs": 87,
              "bootstrap_draws": 5000,
              "positive_median": 0.9187279151943377,
              "control_median": 0.5689922710474147,
              "paired_mean_difference": 0.24628127694259183,
              "matched_separation_rate": 0.8275862068965517,
              "cluster_bootstrap_ci95": [
                0.18630666822376413,
                0.30531049143854294
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 30000,
            "summary": {
              "pairs": 87,
              "bootstrap_draws": 5000,
              "positive_median": 0.9240282685513441,
              "control_median": 0.6058251425489355,
              "paired_mean_difference": 0.20731953012203794,
              "matched_separation_rate": 0.7701149425287356,
              "cluster_bootstrap_ci95": [
                0.14522854382527461,
                0.26897351046132284
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 60000,
            "summary": {
              "pairs": 87,
              "bootstrap_draws": 5000,
              "positive_median": 0.9142011834322122,
              "control_median": 0.632932329972296,
              "paired_mean_difference": 0.18832000222168913,
              "matched_separation_rate": 0.7126436781609196,
              "cluster_bootstrap_ci95": [
                0.12207853320738313,
                0.25534679124149207
              ]
            }
          }
        ]
      }
    },
    "7-10s": {
      "positive_count": 57,
      "control_supported_positive_count": 57,
      "analysis": {
        "conclusion": "inconclusive",
        "windows_ms": [
          2000,
          5000,
          10000,
          30000,
          60000
        ],
        "results": [
          {
            "split": "development",
            "window_ms": 2000,
            "summary": {
              "pairs": 38,
              "bootstrap_draws": 5000,
              "positive_median": 0.5629528985486698,
              "control_median": 0.5759093369178826,
              "paired_mean_difference": -0.033982529447597484,
              "matched_separation_rate": 0.47368421052631576,
              "cluster_bootstrap_ci95": [
                -0.15645680284731736,
                0.09037222047477936
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 5000,
            "summary": {
              "pairs": 38,
              "bootstrap_draws": 5000,
              "positive_median": 0.6343388960203921,
              "control_median": 0.6220063984190742,
              "paired_mean_difference": -0.0025341386449806214,
              "matched_separation_rate": 0.5263157894736842,
              "cluster_bootstrap_ci95": [
                -0.11554476380587683,
                0.10851029716659552
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 10000,
            "summary": {
              "pairs": 38,
              "bootstrap_draws": 5000,
              "positive_median": 0.7973809909325406,
              "control_median": 0.6705078675626286,
              "paired_mean_difference": 0.0843694711125296,
              "matched_separation_rate": 0.6842105263157895,
              "cluster_bootstrap_ci95": [
                -0.01484230606496287,
                0.17569198664538987
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 30000,
            "summary": {
              "pairs": 38,
              "bootstrap_draws": 5000,
              "positive_median": 0.8162160775666605,
              "control_median": 0.6293924417620471,
              "paired_mean_difference": 0.08537061138066568,
              "matched_separation_rate": 0.6578947368421053,
              "cluster_bootstrap_ci95": [
                -0.014226596351206421,
                0.18224992794635295
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 60000,
            "summary": {
              "pairs": 38,
              "bootstrap_draws": 5000,
              "positive_median": 0.8109577922078328,
              "control_median": 0.6070033469503813,
              "paired_mean_difference": 0.09914970059875304,
              "matched_separation_rate": 0.6578947368421053,
              "cluster_bootstrap_ci95": [
                -0.017189665890412834,
                0.20903629514863556
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 2000,
            "summary": {
              "pairs": 19,
              "bootstrap_draws": 5000,
              "positive_median": 0.600000000000485,
              "control_median": 0.536762642120624,
              "paired_mean_difference": -0.03676370982474262,
              "matched_separation_rate": 0.5789473684210527,
              "cluster_bootstrap_ci95": [
                -0.2297197273598459,
                0.15099118026748035
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 5000,
            "summary": {
              "pairs": 19,
              "bootstrap_draws": 5000,
              "positive_median": 0.7499999999998542,
              "control_median": 0.5268081422990917,
              "paired_mean_difference": 0.036616398399496035,
              "matched_separation_rate": 0.5789473684210527,
              "cluster_bootstrap_ci95": [
                -0.1304843798410353,
                0.1967235994345879
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 10000,
            "summary": {
              "pairs": 19,
              "bootstrap_draws": 5000,
              "positive_median": 0.7954545454544515,
              "control_median": 0.5794958981587752,
              "paired_mean_difference": 0.1382033924081595,
              "matched_separation_rate": 0.6842105263157895,
              "cluster_bootstrap_ci95": [
                -0.005682528982785082,
                0.2668920633936185
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 30000,
            "summary": {
              "pairs": 19,
              "bootstrap_draws": 5000,
              "positive_median": 0.7227722772280348,
              "control_median": 0.5575175448785344,
              "paired_mean_difference": 0.07506476572062536,
              "matched_separation_rate": 0.5789473684210527,
              "cluster_bootstrap_ci95": [
                -0.07635902557406787,
                0.21787490416359517
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 60000,
            "summary": {
              "pairs": 19,
              "bootstrap_draws": 5000,
              "positive_median": 0.4657980456021523,
              "control_median": 0.5609041728297867,
              "paired_mean_difference": -0.013001464353069515,
              "matched_separation_rate": 0.42105263157894735,
              "cluster_bootstrap_ci95": [
                -0.15822724826108792,
                0.13668641870791018
              ]
            }
          }
        ]
      }
    },
    "10-30s": {
      "positive_count": 148,
      "control_supported_positive_count": 148,
      "analysis": {
        "conclusion": "weak",
        "windows_ms": [
          2000,
          5000,
          10000,
          30000,
          60000
        ],
        "results": [
          {
            "split": "development",
            "window_ms": 2000,
            "summary": {
              "pairs": 74,
              "bootstrap_draws": 5000,
              "positive_median": 0.44949494949401225,
              "control_median": 0.5198968134257246,
              "paired_mean_difference": -0.07666061203751391,
              "matched_separation_rate": 0.47297297297297297,
              "cluster_bootstrap_ci95": [
                -0.17653699591327657,
                0.026210171642977675
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 5000,
            "summary": {
              "pairs": 74,
              "bootstrap_draws": 5000,
              "positive_median": 0.5672905525846811,
              "control_median": 0.5604034286936199,
              "paired_mean_difference": -0.04390636504083083,
              "matched_separation_rate": 0.5,
              "cluster_bootstrap_ci95": [
                -0.14369086405956363,
                0.05600081204096802
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 10000,
            "summary": {
              "pairs": 74,
              "bootstrap_draws": 5000,
              "positive_median": 0.674166091557986,
              "control_median": 0.6367334290557194,
              "paired_mean_difference": -0.03635565357973315,
              "matched_separation_rate": 0.5135135135135135,
              "cluster_bootstrap_ci95": [
                -0.1286931576392912,
                0.05549124369021117
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 30000,
            "summary": {
              "pairs": 74,
              "bootstrap_draws": 5000,
              "positive_median": 0.769714285714424,
              "control_median": 0.7014898633070599,
              "paired_mean_difference": -0.0007228068377242481,
              "matched_separation_rate": 0.5945945945945946,
              "cluster_bootstrap_ci95": [
                -0.07604241731461546,
                0.0741024120895845
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 60000,
            "summary": {
              "pairs": 74,
              "bootstrap_draws": 5000,
              "positive_median": 0.7802636430678479,
              "control_median": 0.6719852753545124,
              "paired_mean_difference": 0.0031074475466881936,
              "matched_separation_rate": 0.6081081081081081,
              "cluster_bootstrap_ci95": [
                -0.06815363096345849,
                0.07395742478604832
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 2000,
            "summary": {
              "pairs": 72,
              "bootstrap_draws": 5000,
              "positive_median": 0.5346644010190698,
              "control_median": 0.5018090766011273,
              "paired_mean_difference": 0.03094375877231006,
              "matched_separation_rate": 0.5138888888888888,
              "cluster_bootstrap_ci95": [
                -0.07188702474969785,
                0.1301621273212011
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 5000,
            "summary": {
              "pairs": 72,
              "bootstrap_draws": 5000,
              "positive_median": 0.6495535714291139,
              "control_median": 0.5288388336575132,
              "paired_mean_difference": 0.05813220949113031,
              "matched_separation_rate": 0.5972222222222222,
              "cluster_bootstrap_ci95": [
                -0.033575350353095564,
                0.1494209881674287
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 10000,
            "summary": {
              "pairs": 72,
              "bootstrap_draws": 5000,
              "positive_median": 0.7018168242911353,
              "control_median": 0.5640665917884748,
              "paired_mean_difference": 0.046158860064767604,
              "matched_separation_rate": 0.625,
              "cluster_bootstrap_ci95": [
                -0.04571443470437064,
                0.1350363083708862
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 30000,
            "summary": {
              "pairs": 72,
              "bootstrap_draws": 5000,
              "positive_median": 0.8023903503075414,
              "control_median": 0.6063512810346863,
              "paired_mean_difference": 0.10924020377804303,
              "matched_separation_rate": 0.6527777777777778,
              "cluster_bootstrap_ci95": [
                0.02619296610002967,
                0.1883911261246658
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 60000,
            "summary": {
              "pairs": 72,
              "bootstrap_draws": 5000,
              "positive_median": 0.7330167364017676,
              "control_median": 0.6077995912857344,
              "paired_mean_difference": 0.059757471030966146,
              "matched_separation_rate": 0.5555555555555556,
              "cluster_bootstrap_ci95": [
                -0.01777138564059012,
                0.13528446023869778
              ]
            }
          }
        ]
      }
    },
    "30-60s": {
      "positive_count": 73,
      "control_supported_positive_count": 73,
      "analysis": {
        "conclusion": "weak",
        "windows_ms": [
          2000,
          5000,
          10000,
          30000,
          60000
        ],
        "results": [
          {
            "split": "development",
            "window_ms": 2000,
            "summary": {
              "pairs": 34,
              "bootstrap_draws": 5000,
              "positive_median": 0.3633879781457272,
              "control_median": 0.4914959707797645,
              "paired_mean_difference": -0.03568969711889029,
              "matched_separation_rate": 0.5,
              "cluster_bootstrap_ci95": [
                -0.16828471405857512,
                0.101792277892753
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 5000,
            "summary": {
              "pairs": 34,
              "bootstrap_draws": 5000,
              "positive_median": 0.5401785714290064,
              "control_median": 0.5327733880736614,
              "paired_mean_difference": 0.037430799857234874,
              "matched_separation_rate": 0.5588235294117647,
              "cluster_bootstrap_ci95": [
                -0.07910068811402746,
                0.15243218823217108
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 10000,
            "summary": {
              "pairs": 34,
              "bootstrap_draws": 5000,
              "positive_median": 0.6482683982688603,
              "control_median": 0.6002341971059795,
              "paired_mean_difference": 0.028860799887260855,
              "matched_separation_rate": 0.5588235294117647,
              "cluster_bootstrap_ci95": [
                -0.0904347497059271,
                0.1454293076529769
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 30000,
            "summary": {
              "pairs": 34,
              "bootstrap_draws": 5000,
              "positive_median": 0.7631336405532216,
              "control_median": 0.6351530060904871,
              "paired_mean_difference": 0.06451480732126158,
              "matched_separation_rate": 0.6470588235294118,
              "cluster_bootstrap_ci95": [
                -0.05703522420304045,
                0.18115675553469393
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 60000,
            "summary": {
              "pairs": 34,
              "bootstrap_draws": 5000,
              "positive_median": 0.8297979570713543,
              "control_median": 0.6215469179860219,
              "paired_mean_difference": 0.1443176646127738,
              "matched_separation_rate": 0.6764705882352942,
              "cluster_bootstrap_ci95": [
                0.05585262776882888,
                0.23232979719809382
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 2000,
            "summary": {
              "pairs": 38,
              "bootstrap_draws": 5000,
              "positive_median": 0.5952935694317392,
              "control_median": 0.5332590618104969,
              "paired_mean_difference": 0.004256083061304022,
              "matched_separation_rate": 0.5,
              "cluster_bootstrap_ci95": [
                -0.12729802192991266,
                0.14078201754179834
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 5000,
            "summary": {
              "pairs": 39,
              "bootstrap_draws": 5000,
              "positive_median": 0.46153846153092726,
              "control_median": 0.5503030303034387,
              "paired_mean_difference": -0.022766105761639628,
              "matched_separation_rate": 0.48717948717948717,
              "cluster_bootstrap_ci95": [
                -0.13891271957884324,
                0.09168189127694369
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 10000,
            "summary": {
              "pairs": 39,
              "bootstrap_draws": 5000,
              "positive_median": 0.4210526315794513,
              "control_median": 0.6087198026298081,
              "paired_mean_difference": -0.06169507305877509,
              "matched_separation_rate": 0.41025641025641024,
              "cluster_bootstrap_ci95": [
                -0.18043698621952553,
                0.06220120330541586
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 30000,
            "summary": {
              "pairs": 39,
              "bootstrap_draws": 5000,
              "positive_median": 0.6228813559322524,
              "control_median": 0.5983456971794057,
              "paired_mean_difference": -0.0071703696294820405,
              "matched_separation_rate": 0.4358974358974359,
              "cluster_bootstrap_ci95": [
                -0.11286774938681705,
                0.09702504137622933
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 60000,
            "summary": {
              "pairs": 39,
              "bootstrap_draws": 5000,
              "positive_median": 0.7964959568733856,
              "control_median": 0.621986530189323,
              "paired_mean_difference": 0.10094085624829327,
              "matched_separation_rate": 0.5897435897435898,
              "cluster_bootstrap_ci95": [
                0.005023668902036558,
                0.1945408772460378
              ]
            }
          }
        ]
      }
    },
    ">60s": {
      "positive_count": 122,
      "control_supported_positive_count": 122,
      "analysis": {
        "conclusion": "inconclusive",
        "windows_ms": [
          2000,
          5000,
          10000,
          30000,
          60000
        ],
        "results": [
          {
            "split": "development",
            "window_ms": 2000,
            "summary": {
              "pairs": 45,
              "bootstrap_draws": 5000,
              "positive_median": 0.730158730159051,
              "control_median": 0.48380719948677064,
              "paired_mean_difference": 0.1551946079082458,
              "matched_separation_rate": 0.6888888888888889,
              "cluster_bootstrap_ci95": [
                0.02590518633519166,
                0.2701133273472304
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 5000,
            "summary": {
              "pairs": 45,
              "bootstrap_draws": 5000,
              "positive_median": 0.7272727272742305,
              "control_median": 0.49420335761825795,
              "paired_mean_difference": 0.1327002294231957,
              "matched_separation_rate": 0.6,
              "cluster_bootstrap_ci95": [
                0.033290744938470895,
                0.23227545279150302
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 10000,
            "summary": {
              "pairs": 45,
              "bootstrap_draws": 5000,
              "positive_median": 0.7968750000010658,
              "control_median": 0.5340386498038533,
              "paired_mean_difference": 0.11333071296429055,
              "matched_separation_rate": 0.6,
              "cluster_bootstrap_ci95": [
                0.0028894662036515707,
                0.2141920552268353
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 30000,
            "summary": {
              "pairs": 45,
              "bootstrap_draws": 5000,
              "positive_median": 0.7767857142857831,
              "control_median": 0.5931978582377441,
              "paired_mean_difference": 0.060560850171916494,
              "matched_separation_rate": 0.5777777777777777,
              "cluster_bootstrap_ci95": [
                -0.04591155569906952,
                0.16470656177848744
              ]
            }
          },
          {
            "split": "development",
            "window_ms": 60000,
            "summary": {
              "pairs": 45,
              "bootstrap_draws": 5000,
              "positive_median": 0.7252252252249946,
              "control_median": 0.6263360157748479,
              "paired_mean_difference": -0.0011277906844722727,
              "matched_separation_rate": 0.5555555555555556,
              "cluster_bootstrap_ci95": [
                -0.10579972884420753,
                0.10039249115358692
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 2000,
            "summary": {
              "pairs": 77,
              "bootstrap_draws": 5000,
              "positive_median": 0.33333333332929116,
              "control_median": 0.4466346153844295,
              "paired_mean_difference": -0.01876180418907281,
              "matched_separation_rate": 0.45454545454545453,
              "cluster_bootstrap_ci95": [
                -0.12320133787385776,
                0.08637906854147445
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 5000,
            "summary": {
              "pairs": 77,
              "bootstrap_draws": 5000,
              "positive_median": 0.5249999999993747,
              "control_median": 0.4722131399493373,
              "paired_mean_difference": 0.027064884160774478,
              "matched_separation_rate": 0.5194805194805194,
              "cluster_bootstrap_ci95": [
                -0.07273622244038985,
                0.1269578682400183
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 10000,
            "summary": {
              "pairs": 77,
              "bootstrap_draws": 5000,
              "positive_median": 0.5283018867922262,
              "control_median": 0.5021870604783382,
              "paired_mean_difference": -0.008820677058447583,
              "matched_separation_rate": 0.5064935064935064,
              "cluster_bootstrap_ci95": [
                -0.10374240529521797,
                0.08659662495787057
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 30000,
            "summary": {
              "pairs": 77,
              "bootstrap_draws": 5000,
              "positive_median": 0.5966386554621078,
              "control_median": 0.563623666775263,
              "paired_mean_difference": -0.02384535312095582,
              "matched_separation_rate": 0.5454545454545454,
              "cluster_bootstrap_ci95": [
                -0.11403048160112675,
                0.06497417982449574
              ]
            }
          },
          {
            "split": "holdout",
            "window_ms": 60000,
            "summary": {
              "pairs": 77,
              "bootstrap_draws": 5000,
              "positive_median": 0.611940298507179,
              "control_median": 0.580149155139021,
              "paired_mean_difference": -0.04258447998427584,
              "matched_separation_rate": 0.5064935064935064,
              "cluster_bootstrap_ci95": [
                -0.12604924796528702,
                0.0425516887798818
              ]
            }
          }
        ]
      }
    }
  },
  "inference_note": "Primary inference excludes positive events below seven seconds of pre-transition state age or without eligible risk time. The pooled all-positive result is descriptive only."
}
```
