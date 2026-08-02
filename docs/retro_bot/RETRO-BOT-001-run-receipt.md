# RETRO-BOT-001 Historical Run Receipt

Status: accepted; source objects remain quarantine-only.

Authorization: owner-authorized RETRO historical screening scope, 2026-08-01.

Retention: until project close or earlier owner revocation.

Credential preflight: the registered report and XAUUSD tick object sets were
accepted by the existing RETRO-003 receipt; no credential, cookie, token,
secret, or private-key material was accepted.

## Exact input binding

- Locked machine configuration: `RETRO-BOT-001-config.json`, digest
  `b420d9d014c2cac67461eda9603a200b2a48d0ad1fa0299baaf1c8cdeded5c52`.
- Report object set: 9 registered aliases, manifest digest
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`.
- Tick object set: 39 registered aliases, manifest digest
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.
- The replay runner independently rediscovered exactly one accepted source
  run for each role, verified every alias/hash/path before parsing, and kept
  both runs outside all M5 manifests and gates.

## Run and reproducibility record

- After the DST fail-closed remediation, two fresh aggregate runs were written
  as direct children of the registered ignored RETRO-BOT replay root.
- Both runs passed aggregate schema validation, were byte-identical, and
  produced the identical aggregate digest
  `09146b45382dcf4380c575e96151eaf1971f4947059c46e014c431b2c4e38fe5`.
- The tracked result was generated only by the result writer from the first
  privacy-validated aggregate payload.

No raw rows, prices, tickets, detailed timelines, credentials, source paths,
or ignored source files are retained in this receipt. The result remains
descriptive RETRO evidence and is not an M5 input, model, evaluation, or gate.
