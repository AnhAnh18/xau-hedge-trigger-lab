# State Reconstruction Report

- Unique positions: 7086
- Closed / open: 7084 / 2
- Snapshot rows merged: 6
- Exceptions: 630

## Boundary accounting

- Unlocks / re-hedges: 6276 / 6277
- The timeline starts FLAT and ends HEDGED_1X1; its final event is REHEDGE_SELL, so one re-hedge has no subsequent observed unlock within the report boundary.

## Event accounting

- classified_standard: 12006
- multi_position: 1524
- ambiguous_ordering: 630
- boundary: 8
- unbalanced_hedge: 2
- total: 14170
- event_total: 14170

## Event counts

- UNLOCK_TO_BUY: 3254
- REHEDGE_SELL: 3253
- REHEDGE_BUY: 3024
- UNLOCK_TO_SELL: 3022
- UNCLASSIFIED: 803
- OPEN_ADDITIONAL_BUY: 409
- OPEN_ADDITIONAL_SELL: 394
- CLOSE_TO_FLAT: 5
- INITIAL_OPEN_BUY: 3
- INITIAL_OPEN_SELL: 3
