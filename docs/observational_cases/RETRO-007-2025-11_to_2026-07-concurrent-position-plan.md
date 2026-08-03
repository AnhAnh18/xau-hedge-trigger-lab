# RETRO-007 Plan

1. Verify the RETRO-003 parent manifests, exact quarantine roots, aliases,
   suffixes, and SHA-256 values before opening any source.
2. Parse the nine reports in memory, deduplicate position ids across monthly
   snapshots, fail closed on conflicts, and build positive-duration Buy/Sell
   interval counts without retaining row details.
3. Stream the 39 tick aliases once to detect valid UTC gaps greater than 60
   seconds; classify weekend-opening candidates under UTC+2 and UTC+3 and
   associate only fixed 120-second post-gap windows.
4. Produce a redacted self-hashed aggregate with maximum concurrent totals,
   Monday/non-Monday buckets, definite/possible multi-position counts, gap
   buckets, censor/conflict counts, and explicit M5/privacy attestations.
5. Validate deterministic repeatability, synthetic interval edge cases,
   privacy/firewall behavior, compileability, and `git diff --check`; obtain an
   independent review before recording the result.

No raw row, detailed timeline, price, ticket, path, credential, M5 input, or
live/demo surface may be retained or printed.
