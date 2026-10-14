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

## G13: Bitcoin wallets beyond the common case

**What is missing:** tried against live nodes (Fulcrum, electrs, Bitcoin Core 27 and later, a self-hosted mempool); pinning an Electrum server's certificate rather than accepting the one it presents; taproot (`tr()`) and multisig wallets from their descriptors; matching a transfer out of a wallet with the transfer in at an exchange or another wallet (S1.7) so the basis carries over; the network fee as a disposal of its own for taxes; and a reorganised chain removing a transaction already recorded.

**Touches:** S1.6, S1.7, S8.

## G14: Linked households beyond the first build

**What is missing:** the window's fuller screens (Positions, a projection's charts, a giving plan's months and organisations, a budget's cash flow and recurring payments), which each need their documents added to what the source sends; a separate listener port for `/link` (it is served under the public address's `/link/` path, for a reverse proxy to expose apart); links tried across two real networks (an overlay such as Tailscale, and a forwarded port), not only two servers on one host; the linked window in the generated mockup; and how much a large household's first full snapshot weighs.

**Touches:** S11.2, S11.3.1, S12.9, S12.10.

## G15: What database pruning's yearly summaries hold

**What is missing:** what the yearly summaries left by database pruning (S14.10.5) hold beyond income and spending by category, gifts, donations and contributions per owner and year: totals by payee, income by holding, a closed account's yearly balances; and which reports and charts read them for the pruned years.

**Touches:** S5, S7, S14.10.

## G16: How each record decides it has ended

**What is missing:** the end of each kind of record beyond the few in `schema.md` §6.2, and what a record shows for one it names that has been deleted or pruned. A gift to a person who was deleted is still money spent, and stays with the year's spending, but who it was given to is open: kept as the person's name at the time, shown as a deleted person, or left blank. The same question arises wherever a record outlives what it names: a donation and its organisation, a transaction and its category or payee, a budget line and its category, a share and its user, a contribution and its 529 plan's beneficiary.

**Touches:** S1, S5, S6, S7, S14.10, `schema.md` §4, §6.

## G17: Bitcoin amounts in sats

**What is missing:** bitcoin amounts as whole numbers of sats, the unit bitcoin itself counts in: stored and sent as integers (on-chain balances, transaction amounts, fees, a bitcoin lot's units), which JSON and the browser carry exactly as plain numbers, since every possible amount is below 2^53. A Profile preference shows them as **sats** (`12,345,678 sats`) or **BTC** (`0.12345678 BTC`), the conversion done only in formatting. Today they are decimal quantities like any other (S13.8.2).

**Touches:** S1.6, S3, S12, S13.8.2, `schema.md`.

## G18: External connectors

**Needed for the first release** (S17.9).

**What is missing:** small programs, each short enough for a person to read in full and trust, that hold an institution's credentials or personal access token outside MoneyKata, fetch what the institution offers (OFX, CSV, PDF statements), and post it to MoneyKata's import, so an account stays current without downloading and uploading by hand. To specify: where a connector runs (on the host, beside the server, or on a person's own machine) and how it keeps its credentials; the access token it posts with, limited to importing into the accounts it names, since today's tokens only read (S10.9); how its imports are checked and recorded (Activity, an alert when one fails); and the first connectors, for the average cases (a Schwab brokerage account, a UMB bank account).

**Touches:** S1.3, S10.9, S13.7, S17.9.

## G19: Other option price sources

**For later consideration.** CBOE's delayed quotes (S4.5) aren't an official API and could change or close. The alternatives, each to be tried before it is relied on:

- **Schwab Trader API** (official, free with a Schwab account): real-time chains and marks; its sign-in token lasts seven days, so it belongs in an external connector (G18), not the server.
- **MarketData.app** (official, a free key with a daily request limit): chains and end-of-day quotes.
- **Massive** (formerly Polygon.io), Basic plan: shipped as the fallback (S4.3) but not yet tried with a live key: its limits, its history for expired contracts.
- **Tradier** (official, free with an account): delayed chains.

**Touches:** S4.3, S4.5, G18.
