# RETRO-LIVE-EVIDENCE-002 Expansion Result

Status: complete capture, fail-closed at `insufficient-actionful-coverage`.
This result is RETRO-only and does not authorize E-003/E-004 real-source work,
shadow observation, demo/canary execution, live execution, or any M5 input,
model, threshold, or gate change.

Both seasonal scopes used their separately authorized source receipt and the
same frozen E-001 gate registry. Only redacted aggregates and digest-only
capture receipts were retained; no raw rows, credentials, private paths, or
execution artifacts were emitted.

## Winter scope

- Receipt: `37d3d84e52b43ad4bb318c901df12d42edef278c22fcef8317373bd6c3f9f96d`
- UTC window: `[2025-10-31T22:00:00.000000Z, 2026-03-27T22:00:00.000000Z)`
- Clock: `UTC+2-winter`; source aliases: 9 reports and 22 ticks
- Replayed twice with canonical UTF-8 output; file SHA-256:
  `324fd0e62fe1cc3d4d66d40e3acd7299ca54a8b1dc4bccdb762376bab7a42e84`
- Aggregate SHA-256:
  `72d8d2b75ecb72521293ffb969f376a40a3cd63a49a3de5b9165364c7d47a733`
- 1,779 cycles; 1,476 eligible; 303 censored
- Category counts: normal hedge 353, one-leg recovery 1,476,
  Monday-gap 0, variable-lot 1, wide-spread 6
- Eligible buy/sell actions: 1,820 / 1,858
- Status: `insufficient-actionful-coverage` (Monday-gap and variable-lot
  thresholds are not met)
- Capture-receipt SHA-256:
  `d78315b3e501719f58d3855fdac8ec0f3d42076caa563b3fcd58d2804feb9e1e`

## Summer-transition scope

- Receipt: `3a59c1af6e80f490829adef004cf84925c269db124a57ef8c1b8cc16bbba13d8`
- UTC window: `[2026-04-03T21:00:00.000000Z, 2026-04-24T21:00:00.000000Z)`
- Clock: `UTC+3-summer`; transition interval is censored; source aliases:
  9 reports and 3 ticks
- Replayed twice with canonical UTF-8 output; file SHA-256:
  `665dfa00d91df6d61be3c6edb6ed0341a75feade718e6b5b2becb226f7db1922`
- Aggregate SHA-256:
  `aad7c8a3a15b000d6efe4765211705e4a365a0d4950155cd6c88344aa4db1419`
- 9 cycles; 0 eligible; all 9 censored
- Eligible category/action counts are all zero because no uncensored cycle
  crossed the registered transition scope
- Status: `insufficient-actionful-coverage`
- Capture-receipt SHA-256:
  `962067f70d08d30dafe4e0e9dca38e9fdfb25ed279c40ab79a3a938c96b78ce1`

## Verification

- Focused E-002 tests: 17 passed
- Full regression: 488 passed, one pre-existing pandas warning
- `compileall` and scoped `git diff --check`: passed
- The stdin capture verifier accepted both seasonal aggregates and their
  receipt bindings.
- Fresh independent post-fix review: `PASS`, with no P0-P3 findings

The expanded population still lacks the frozen Monday-gap and variable-lot
actionful slices. E-003/E-004 real-source capture and every downstream
readiness gate therefore remain blocked.
