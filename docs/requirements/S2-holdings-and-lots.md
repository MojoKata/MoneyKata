# S2. Holdings, lots and transactions

1. **Instruments** are kept once per server: symbol, name, class (`cash`, `equity`, `etf`,
   `mutual-fund`, `money-market`, `bond`, `option`, `crypto`, `metal`, `other`), and for
   options the underlying, right (call/put), strike, expiry and multiplier (100 by default). An
   option's symbol follows OCC (`AAPL  261218C00250000`); it is stored as people read it, `AAPL
   18DEC26 250 C`, and shown as `AAPL 18 Dec 26 250 C`.
2. **Lots** are created by buys and by transfers in with a cost basis. A transfer in without a
   cost basis asks for one, and the lot is marked *basis missing* until it has one. Taxes
   lists these (S8.4).
3. **Sales consume lots** by the account's **lot method**: FIFO (the default), LIFO, HIFO,
   specific identification (chosen per sale), or **average cost** (mutual funds, and crypto
   where elected). The method in force at the sale is recorded on it, however the sale arrives
   (typed, imported or synced); changing an account's method applies to the sales after the
   change, and the wash sales are worked out again (S3.8.4).
4. **Corporate actions**: splits, reverse splits, symbol changes, spin-offs (manual basis
   allocation), mergers (cash and/or stock) and return of capital adjust lots, never history.
   Return of capital is spread over every lot of the holding by quantity, a lot without a basis
   keeping its share until its basis is entered; what exceeds a lot's basis is a capital gain.
5. **Dividends and interest**: qualified and ordinary dividends, reinvestment (a dividend plus
   a buy), and capital-gain distributions, with the classification the 1099 will use.
6. **Bank transactions** have a payee (normalised by **payee rules**), a category (S7.2), an
   optional split across categories, a memo, tags, and receipts.
7. **Categorisation rules**: an ordered list per user, first match wins. A rule matches the
   payee (text or `re:`), amount range, account and direction, and sets the category, tags and payee. Rules apply on import, and on demand to
   the uncategorised transactions.
8. **Editing history** is allowed. Every derived figure (balances, lots, gains, budgets,
   charts) follows on the next request. An edit that changes a closed tax year's realized
   gains asks for confirmation first.
