# RETRO-LIVE-EVIDENCE E-002 Expansion Request

Status: proposal only; this document is not an owner authorization and does
not permit source access, hashing, parsing, copying, or retention.

## Why expansion is needed

The authorized summer capture completed with a frozen fail-closed result:
2,038 cycles, 2,016 eligible cycles, normal hedge 8, one-leg recovery 2,016,
wide spread 593, Monday gap 0, and variable lot 0. The E-001 actionful
population therefore remains insufficient for E-003 and E-004.

## Proposed bounded source set

If approved, use only the already accepted RETRO-003 archive objects:

- the same nine report aliases `report-001.html` through `report-009.html`;
- the 25 weekly tick aliases from
  `XAUUSD_ticks_2025-11-01_to_2025-11-08.csv` through
  `XAUUSD_ticks_2026-04-18_to_2026-04-25.csv` in addition to the 14 aliases
  already bound by E-002;
- no XLSX/PNG companions, journals, caches, M1 objects, credentials, or
  execution artifacts.

The source hashes and byte counts must be copied into a new case-specific
receipt from the accepted RETRO-003 receipt, then independently revalidated
against the parent manifests before parsing. The current E-002 receipt must
not be edited or reused as the authorization for this expansion.

## Required owner decisions

The owner must explicitly approve a new authorization ID, the exact aliases,
the retention deadline, and the seasonal clock treatment. The recommended
shape is two disjoint receipts so daylight-saving assumptions cannot be hidden:

1. a winter case under `UTC+2-winter`;
2. a summer extension under `UTC+3-summer`, with transition boundaries
   censored unless the owner registers an exact UTC mapping.

Each receipt must state the half-open UTC population, exact field allowlists,
parser/canonicalization versions, redacted-only retention, untouched M5
inputs/models/thresholds/gates, and `execution_surface_authorized=false`.

## Gate behavior

Even after approval, the implementation must preserve the frozen E-001
thresholds. If the expanded capture still lacks any required category, it
must remain `insufficient-actionful-coverage`; E-003/E-004, E-005 shadow, and
E-006 readiness must not be promoted.
