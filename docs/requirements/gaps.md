# Gaps

Areas the requirements name but don't yet specify. Each has a lasting id: a gap that is
closed is removed, its text goes into the section it belongs to, and its id is never used
again. A new gap takes the next number. The [README](README.md#gaps) lists them.

## G1: Link protocol and version skew

**What is missing:** `docs/link-protocol.md`: the messages, their signing, and what two linked servers on different MoneyKata versions do.

**Touches:** S11.

## G2: Web security in one place

**What is missing:** the policies of S13.7 are proposed and await review.

**Touches:** S13, S14.

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
