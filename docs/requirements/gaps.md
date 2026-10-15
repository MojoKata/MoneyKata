# Gaps

Areas the requirements name but don't yet specify. Each has a lasting id: a gap that is
closed is removed, its text goes into the section it belongs to, and its id is never used
again. A new gap takes the next number. The [README](README.md#gaps) lists them.

## G8: Reading a brokerage statement's trades

**What is missing:** reading the trades (buys and sells) on a brokerage statement, its options activity and its corporate actions (splits, mergers, spin-offs). A misread quantity or price would corrupt lots and gains, so this waits until the summary, positions and cash activity (S1.3.3.8) have proven themselves; until then each such line is shown as not read, with its figures offered to the trade dialog.

**Touches:** S1.3.3.8, S3.

## G12: Adjusted contracts and capital at risk

**What is missing:** how a contract adjusted after a split or a special dividend is named and priced (its OCC root changes, and CBOE lists it under the new one); and capital at risk for spreads and covered calls, which wait on strategies (S3.5). The wash-sale cases the rules leave unsettled are flagged for review (S3.8.5). Option prices come from CBOE's delayed quotes (S4.5); other sources are G19.

**Touches:** S3.5, S3.8, S3.9, S4.5.

## G19: Other option price sources

**For later consideration.** CBOE's delayed quotes (S4.5) aren't an official API and could change or close. The alternatives, each to be tried before it is relied on:

- **Schwab Trader API** (official, free with a Schwab account): real-time chains and marks; its sign-in token lasts seven days, so it belongs in a driver of the MoneyKata Connector (S18), not the server.
- **MarketData.app** (official, a free key with a daily request limit): chains and end-of-day quotes.
- **Massive** (formerly Polygon.io), Basic plan: shipped as the fallback (S4.3) but not yet tried with a live key: its limits, its history for expired contracts.
- **Tradier** (official, free with an account): delayed chains.

**Touches:** S4.3, S4.5, S18.
