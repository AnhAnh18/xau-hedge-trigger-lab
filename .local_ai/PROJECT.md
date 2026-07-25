# Project

## Goal

Reverse-engineer and reproduce the observable behavior of an XAUUSD alternating hedge-rotation strategy.

## Primary questions

1. When hedged, what condition causes the bot to close Buy or Sell?
2. When one leg remains, what condition causes the bot to reopen the opposite leg?
3. Is the trigger based on price action, ticks, P/L, or an external source?
4. Does the logic work outside the observed sample?

## Non-goals

- Do not assume the original account's profitability can be reproduced.
- Do not use martingale or multi-level grid logic.
- Do not optimize for profit before reproducing behavior.
