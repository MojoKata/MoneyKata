# Gaps

Areas the requirements name but don't yet specify. Each has a lasting id: a gap that is
closed is removed, its text goes into the section it belongs to, and its id is never used
again. A new gap takes the next number. The [README](README.md#gaps) lists them.

## G5: Data sunset

**What is missing:** how data older than the seven-year audit period is retired: what goes, what is summarised, who decides, and how it is confirmed (S14.10).

**Touches:** S14, `schema.md` §4.

## G6: Operations

**What is missing:** `docs/operations.md`: upgrades and migrations in the Docker image, health checks, logs, monitoring, restore drills.

**Touches:** S13, S15, S17.8.

## G7: API conventions and reference

**What is missing:** the conventions of S13.8 are proposed and await review; `docs/api.md` grows with the code, beside the generated OpenAPI, and documents the MCP tools.

**Touches:** S10.9, S13, S17.5.

## G8: Statement import beyond bank and card statements

**What is missing:** brokerage statements (a Schwab brokerage statement's positions, trades and income, which OFX and CSV cover today), statements of several accounts in one file, and learning column positions rather than section headings for layouts without sections or a running balance.

**Touches:** S1.3.

## G10: Statement intervals per account

**What is missing:** the interval at which each account's statements or exports are expected (monthly for a bank or Schwab brokerage account, quarterly for many 401(k) plans), how it is set or learned from the imports, and the alert threshold that follows from it.

**Touches:** S1.3, S1.11, S12.11.

## G12: Option prices and wash-sale edges

**What is missing:** an option price source tried against a live Massive key (the Basic plan's limits, its history for expired contracts, and how an adjusted contract after a split is named); index and weekly options' tickers; wash sales across a short sale, a loss on an option itself, and a replacement bought through an option assigned or exercised; and capital at risk for spreads and covered calls, which wait on strategies (S3.5).

**Touches:** S3.5, S3.8, S3.9, S4.5.

## G13: Bitcoin wallets beyond the common case

**What is missing:** tried against live nodes (Fulcrum, electrs, Bitcoin Core 27 and later, a self-hosted mempool); pinning an Electrum server's certificate rather than accepting the one it presents; taproot (`tr()`) and multisig wallets from their descriptors; matching a transfer out of a wallet with the transfer in at an exchange or another wallet (S1.7) so the basis carries over; the network fee as a disposal of its own for taxes; and a reorganised chain removing a transaction already recorded.

**Touches:** S1.6, S1.7, S8.

## G14: Linked households beyond the first build

**What is missing:** the window's fuller screens (Positions, a projection's charts, a giving plan's months and organisations, a budget's cash flow and recurring payments), which each need their documents added to what the source sends; a separate listener port for `/link` (it is served under the public address's `/link/` path, for a reverse proxy to expose apart); links tried across two real networks (an overlay such as Tailscale, and a forwarded port), not only two servers on one host; the linked window in the generated mockup; and how much a large household's first full snapshot weighs.

**Touches:** S11.2, S11.3.1, S12.9, S12.10.
