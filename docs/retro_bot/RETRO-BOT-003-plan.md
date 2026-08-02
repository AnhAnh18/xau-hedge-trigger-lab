# RETRO-BOT-003 Plan

1. Reuse the locked RB-006 configuration and paper outcome implementation.
2. Wrap interval outcomes in sequence order, rejecting overlap and invalid
   chronology without sorting or lookahead.
3. Reduce outcomes to privacy-validated per-clock/policy accounting with
   total/eligible/action/marked/censored/overlap/invalid counts and return
   bands.
4. Add a contained CLI, ignored multi-cycle run root, and tracked redacted
   result writer.
5. Run synthetic focused tests and existing RETRO-BOT validation only; do not
   run historical raw replay.
