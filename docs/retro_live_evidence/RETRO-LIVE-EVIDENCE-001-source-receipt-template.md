# RETRO-LIVE-EVIDENCE-001 Source Receipt Template

This template is intentionally unfilled. It is not a source authorization and
does not identify any collected data.

Required fields for a future E-002 receipt:

- `authorization_id`
- `source_aliases`
- `object_types`
- `sha256_by_alias`
- `byte_count_by_alias`
- `population_utc_half_open`
- `source_timezone_code`
- `allowed_fields`
- `canonicalization_version`
- `parser_version`
- `retention`
- `receipt_sha256`

Aliases must be generated, paths must never be retained, and every hash/window
or field mismatch is a hard stop.
