# Normalized Dataset Report

## Per-report financial reconciliation

| Report | Positions | Orders | Deals | Profit delta | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| 0507-1107 | 575 | 1149 | 1150 | 0.00 | PASS |
| 1207-1807 | 3118 | 6234 | 6236 | 0.00 | PASS |
| 1907-2507 | 2938 | 5876 | 5876 | 0.00 | PASS |
| 2806-0407 | 453 | 906 | 907 | 0.00 | PASS |

## Reconciliation notes

- 8 'out by' deals map to 4 orders; each of those orders produces two deal rows, explaining the net 4 additional deals.
- Position inventory during tick coverage: 2 + 1046 - 1048 = 0 (PASS).

## Dataset summary

- **reports**: 4
- **positions**: 7084
- **orders**: 14165
- **deals**: 14169
- **open_position_snapshots**: 8
- **deal_order_difference**: 4
- **deal_order_explanation**: 8 'out by' deals map to 4 orders; each of those orders produces two deal rows, explaining the net 4 additional deals.
- **integrity_checks**: {'position_id_unique': True, 'order_id_unique': True, 'deal_id_unique': True, 'closed_position_time_order': True, 'position_open_snapshot_overlap': 0, 'required_volumes_present': True}
- **ticks**: 984883
- **missing_quote_updates**: {'bid': 156759, 'ask': 157568}
- **duplicate_time_msc**: 0
- **symbols**: ['XAUUSD']
- **volume_distribution**: {0.2: 455, 0.3: 6626, 1.0: 3}
- **earliest_trade**: 2026-06-25 23:57:12
- **latest_trade**: 2026-07-24 23:45:31
- **total_profit**: 116167.0
- **total_swap**: -282.22
- **spread_min**: 0.21999999999934516
- **spread_max**: 0.3000000000001819
- **spread_mean**: 0.22645668571799885
- **trade_tick_overlap**: {'tick_first': '2026-07-23 12:00:00.046000', 'tick_last': '2026-07-24 23:56:57.758000', 'active_at_start': 2, 'opens': 1046, 'closes': 1048, 'active_at_end': 0, 'equation_result': 0, 'status': 'PASS'}
