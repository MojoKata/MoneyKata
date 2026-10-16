# Later work

Work planned for after the first release (S17.9.9), with what is already known about it. Each
item has a lasting id (L1, L2, …), kept as gaps' and questions' are. When an item is taken up,
it is specified in its section and removed from here; its id is never used again. The
[README](README.md#later-work) lists them.

## L1: Reading a brokerage statement's trades

**What it is:** reading the trades (buys and sells) on a brokerage statement, its options activity and its corporate actions (splits, mergers, spin-offs). A misread quantity or price would corrupt lots and gains, so this waits until the summary, positions and cash activity (S1.3.3.8) have proven themselves; until then each such line is shown as not read, with its figures offered to the trade dialog.

**Touches:** S1.3.3.8, S3.

## L2: Other option price sources

**What it is:** CBOE's delayed quotes (S4.5) aren't an official API and could change or close. The alternatives, each to be tried before it is relied on:

- **Schwab Trader API** (official, free with a Schwab account): real-time chains and marks; its sign-in token lasts seven days, so it belongs in a driver of the MoneyKata Connector (S18), not the server.
- **MarketData.app** (official, a free key with a daily request limit): chains and end-of-day quotes.
- **Massive** (formerly Polygon.io), Basic plan: shipped as the fallback (S4.3) but not yet tried with a live key: its limits, its history for expired contracts.
- **Tradier** (official, free with an account): delayed chains.

**Touches:** S4.3, S4.5, S18.

## L3: Treasury yields and savings-bond rates

**What it is:** a price source for Treasuries, I bonds and EE bonds from the Treasury's published
yield curve and savings-bond rates (free official data), with its host named in the egress
guard (S13.5). Until then they are priced by hand (S4.3), from TreasuryDirect's figures.

**Touches:** S4.3, S13.5, S16.6.
