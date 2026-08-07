# RETRO-LIVE-EVIDENCE E-004 Ledger Plan

Status: revised after independent critique; implementation may begin only
after this plan is accepted. This is redacted offline governance work. It
does not authorize source access, holdout inspection, or execution.

## Objective

Add a deterministic, redacted, one-shot holdout-consumption ledger primitive
for a future E-004 process. It must bind the frozen E-001 gate, a complete
trusted source-receipt digest, holdout input/fold bindings, and the sealed
E-004 receipt without retaining raw rows or private metadata.

## Frozen protocol

- The ledger is a version-1 JSON envelope with exactly these keys:
  `schema_version`, `case_id`, `context_digest`, `genesis_digest`, `entries`,
  `head_digest`.
- `schema_version` is integer `1`; `case_id` is the governance identifier
  `RETRO-LIVE-EVIDENCE-004`; `genesis_digest` is the fixed SHA-256 digest of
  the canonical object `{"case_id":"RETRO-LIVE-EVIDENCE-004","schema_version":1,"tag":"E004-LEDGER-GENESIS-V1"}`;
  the pinned value is
  `95e50b19d2e41ae107bdcb8fa7d2bf1d7e5c61e100d4d21229f3b8a2c51a3d04`.
- `entries` is an ordered list of at most 1024 objects. Each entry has exactly
  `sequence`, `previous_digest`, `receipt`, `evaluation_proof`,
  `entry_digest`.
- `sequence` starts at 1 and increments by one. Entry zero's
  `previous_digest` is `genesis_digest`; each later entry points to the prior
  `entry_digest`. `entry_digest` covers exactly the canonical payload
  `{sequence, previous_digest, receipt, evaluation_proof}` (excluding
  `entry_digest` itself).
- `head_digest` is the genesis digest for an empty ledger, otherwise the last
  `entry_digest`. No timestamps, process IDs, hostnames, random values, or
  caller-supplied ordering metadata are accepted.
- `context_digest` is the canonical digest of the trusted source and fold
  context (`source_digest`, `fold_order_digest`, `fold_bounds_digest`, plus
  the frozen gate identity). It is fixed for the lifetime of a ledger, is
  excluded from each entry's self-digest, and is included in the envelope
  verification payload; changing it invalidates the envelope and requires a
  new genesis. Its exact payload is
  `{"fold_bounds_digest":...,"fold_order_digest":...,"gate_digest":"4b10421035cdd6920c0d044f521c6ebf78384c588b02d15798299eedc960920d","source_digest":...,"tag":"E004-LEDGER-CONTEXT-V1"}`.
  Each append separately receives an externally trusted `input_digest`, which
  must match that entry's receipt and proof. This permits one ledger to record
  multiple distinct one-shot holdouts under the same source/fold context.
- Structural verification is not a claim of durable history by itself:
  `verify_ledger` and `append_ledger_entry` require an externally pinned
  `expected_head_digest` (the persisted prior head). A non-empty ledger must
  match that anchor exactly; an empty ledger is accepted only with the pinned
  genesis anchor. Rebuilt, shortened, reordered, or truncated envelopes are
  rejected when their head does not match the external anchor. The durable
  caller must persist the anchor and use compare-and-swap before replacing it.
- Canonical bytes use UTF-8 JSON with `ensure_ascii=true`, sorted keys,
  separators `(',', ':')`, `allow_nan=false`, and no trailing newline. Input
  CLI parsing rejects duplicate JSON keys, non-finite constants, unknown
  keys, path-like strings, credentials/private fields, and nested raw rows.
- Nonces are ASCII `[A-Za-z0-9._-]`, length 8-80. Ledger size and nesting are
  bounded before any append.

## Entry authenticity and one-shot semantics

- Every candidate receipt is revalidated with `verify_holdout_block`-equivalent
  logic, including exact `seal_holdout_block` recomputation and
  `receipt_sha256` verification.
- The trusted context is supplied by the caller only as redacted digests and
  must exactly match: `FROZEN_GATE_DIGEST`, trusted source-receipt digest,
  trusted fold-order digest, and trusted fold-bounds digest. Append additionally
  requires a trusted holdout input digest. A supplied hash cannot replace
  receipt validation.
- One ledger is scoped to one trusted source/fold context root plus the pinned
  frozen gate. The envelope stores a `context_digest` derived from the gate,
  source, and fold digests; every
  verify or append call must provide the same externally pinned context and a
  trusted input-digest set covering all entries. A context change requires a
  new ledger/genesis and a new owner-authorized case receipt.
- A ledger rejects both duplicate nonces and duplicate holdout bindings. The
  binding key is `(gate_digest, source_digest, input_digest,
  fold_order_digest, fold_bounds_digest)`; nonce and receipt hash are excluded
  so a new nonce cannot consume the same holdout again.
- Exact canonical retry of an already-present entry is idempotent only when
  every byte of the entry matches and the caller's expected head equals the
  persisted current head. A different nonce, receipt, context, or sequence is
  rejected.
- Failed downstream evaluation must not append or consume a nonce. Append is
  validate-then-commit: the caller passes the expected current head, the
  function validates a successful redacted evaluation proof plus the candidate
  and an explicit `evaluation_succeeded=true` marker, then returns a new
  envelope, and the input envelope is never mutated. A
  durable caller must use compare-and-swap on
  `head_digest`; cross-process atomicity is explicitly limited to that CAS
  protocol, not claimed by the pure function.

## Evaluation proof

`evaluation_proof` is the complete redacted E-004 result accepted by
`verify_holdout_result`, with exactly its frozen result keys. The ledger
rechecks its `aggregate_sha256`, `receipt_sha256`, holdout digest, source
receipt digest, fold digests, and `case_id`; it must match the candidate
receipt and trusted context. A proof with a failed schema/digest check, a
different receipt, or a different context cannot append. The proof is stored
inside the entry as redacted metadata only; no raw rows are accepted.
An evaluated fail-closed `status="hold"` is still a completed evaluation and
may be recorded when `evaluation_succeeded=true`; an exception or incomplete
evaluation cannot provide that marker.

## API and tooling

- Add `src/xau_trigger/retro_live_evidence_004_ledger.py` with pure functions
  for `genesis_digest`, `context_digest`, `seal_ledger_entry`, `verify_ledger`,
  and `append_ledger_entry`.
- Add `scripts/run_retro_live_evidence_004.py` as strict stdin-only JSON
  tooling with two operations: `verify` and `append`. Output is one canonical
  redacted envelope; source files are never opened.
- The CLI accepts a top-level envelope containing the operation, ledger,
  candidate receipt, complete `evaluation_proof` (for append), trusted
  source/fold digests, expected head, and `evaluation_succeeded=true`.
  Both operations require `trusted_input_digests` for the existing ledger;
  append additionally requires `trusted_input_digest` bound to the candidate
  receipt.
  It rejects unknown
  top-level keys, inputs over 2,000,000 UTF-8 bytes, and never writes files.
- Add a tooling-status artifact documenting synthetic-only status, exact
  command protocol, and firewall evidence. Do not add M5 manifests,
  realtime/order imports, `.ex5` files, or source adapters.

## Tests and acceptance gates

- Canonical vectors cover empty genesis, one-entry and two-entry heads,
  nonce/sequence bounds, duplicate keys/non-finite JSON, and exact digest
  bytes. Two independent processes must emit byte-identical output.
- Rejection tests cover nonce reuse, same holdout with a new nonce, receipt
  tampering, source/gate/fold mismatch, reordered/deleted/inserted/truncated
  entries, rewritten predecessor/head, missing or altered external head,
  altered context root, unknown keys, oversized input,
  malformed nested values, path/private/raw content, and M5/execution terms.
- Append failure tests prove no input mutation and no nonce consumption;
  invalid/mismatched evaluation proof and CAS mismatch are rejected. Exact
  canonical retry is accepted only as an unchanged idempotent result; proof
  tampering is a dedicated chain-integrity rejection vector.
- Run focused ledger tests, full `uv run --locked pytest`, `compileall`, and
  scoped `git diff --check`. Obtain an independent implementation review and
  a fresh independent re-review before state/task updates.

## Governance and completion

- Update only E-004 ledger task/state/session artifacts after review PASS.
- State artifacts are `.local_ai/STATUS.md`, `.local_ai/TASKS.md`, and
  `.local_ai/SESSION_LOG.md`; add the next task ID after T-063 and record the
  independent plan/implementation/re-review verdicts and exact commands.
- Preserve the E-002 fail-closed result and all M5/RB firewalls. This ledger
  does not promote E-003/E-004 real fidelity, shadow, demo, canary, or live
  readiness.
- Commit prefix: `E-004:`. Push only after independent review PASS.

## Firewall exception

The mandatory case identifier contains the token `live`. The recursive
firewall may exempt that exact value only in the identity fields
`case_id`/`CASE_ID`; the exemption must never apply to keys or values carrying
source rows, paths, credentials, M5 terms, realtime connectors, or execution
intent.
