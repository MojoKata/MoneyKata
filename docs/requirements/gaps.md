# Gaps

Areas the requirements name but don't yet specify. Each has a lasting id: a gap that is
closed is removed, its text goes into the section it belongs to, and its id is never used
again. A new gap takes the next number. The [README](README.md#gaps) lists them.

## G8: Statement import beyond bank and card statements

**What is missing:** reading a brokerage statement's lines: its positions at the period's end (to check holdings against, as balance anchors check cash, S1.11), its cash activity (contributions, dividends, interest, fees) and its trades. Until then a brokerage statement is kept without reading (S1.3.3.6), and OFX and CSV carry a Schwab brokerage account's activity.

**Touches:** S1.3.

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
