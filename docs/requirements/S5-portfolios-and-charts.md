# S5. Portfolios and charts

1. **A portfolio** is a named set of accounts (or chosen holdings of them), owned by a user
   and shareable like an account (S10). A portfolio may include an account shared with its
   owner at `read`.
   1. **Viewers see only the accounts in it that are shared with them.** The others are
      hidden, and left out of every figure, chart and holding the viewer sees, so the
      portfolio's value is the value of what they can see. This holds across a link too.
   2. **Sharing a portfolio** whose accounts are not all shared with the people chosen: the
      Share dialog names the accounts each of them can't see and offers **Share these
      accounts too** (at read, and only for accounts the owner may share). Declining keeps
      them hidden from those people.
   3. A portfolio never includes an account from a linked server: linked data is shown only
      in its own window (S12.10).
2. **Charts each portfolio has:**
   1. **Value over time** (line or area; 1M, 3M, YTD, 1Y, 5Y, All, and a range brush), with
      contributions shown apart from growth, against a **benchmark** (SPY, VT, a 60/40 mix);
   2. **Allocation** (donut and treemap) by asset class, account type (taxable, deferred,
      free), sector, region, and single holding, against an optional **target allocation**,
      with the drift and a rebalancing suggestion (what to buy or sell, preferring the
      tax-advantaged accounts);
   3. **Performance**: time-weighted and money-weighted (IRR) returns per period, per
      account and per portfolio;
   4. **Income**: dividends and interest by month, trailing twelve months, and forecast;
   5. **Holding detail**: a price chart (line, or candles from daily OHLC where available)
      with the user's buys and sells marked.
3. **Net worth** on the Dashboard: assets minus liabilities over time, with the composition
   stacked by account group.
4. **Charts are drawn in the browser** from series the server computes (`GET
   /ui/api/portfolios/{id}/series?metric=value&range=1Y`). The server does the money
   arithmetic and the browser only draws.
