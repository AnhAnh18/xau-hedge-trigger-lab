# RETRO-BOT-002 Plan

1. Reuse the locked RB-001 config and verified source adapters.
2. Stream each valid tick source once and evaluate four delays across three
   clocks while retaining only first action/mark quote scalars per window;
   never materialize raw rows or write them to disk.
3. Apply fixed quantity-1.0 bid/ask execution and conservative marking at the
   observed re-hedge anchor.
4. Reduce outcomes to a privacy-validated, self-hashed aggregate and render a
   tracked redacted result only from that aggregate.
5. Run focused synthetic tests, the existing suite, and firewall checks.
