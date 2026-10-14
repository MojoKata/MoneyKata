# S4. Prices

1. **What prices must be**: **free** for a household to use, and **daily**. An end-of-day
   close is enough, and a delay of hours is fine: MoneyKata is not a trading app and fetches
   no intraday quotes. A source that needs a paid plan can be added (S4.2), but none is
   required.
2. **Price sources are integrations behind one interface, `TickerSource`.** Each is one module
   in `prices/` that registers itself, so adding a source is adding a module.
   1. **What a source declares**: its name, the instrument classes it serves, whether it
      needs an **API key** (and where to get a free one), its rate limits, and the terms it
      was written against, with the date.
   2. **What it does**: `quotes(instruments) → {instrument: (price, as_of)}`, `history(
      instrument, start, end) → daily closes`, and, where it can, `lookup(symbol)` to check a
      symbol before it is used.
   3. **Settings › Prices** lists the enabled sources, each with its classes, its key
      (*set*, with when and by whom; a key is a secret, S14.4), its order of preference per
      class, its last run and its last error. **Add a source** picks from every source
      MoneyKata ships. A source that needs a key can't be enabled without one.
3. **Starting sources**, chosen for being free and daily. Their terms change, so each is
   checked again when a release ships.

   | Need | Source | Key | Notes |
   | --- | --- | --- | --- |
   | US stocks and ETFs, benchmarks (VT, SPY) | **Tiingo** | free | 500 symbols a month, 50 requests an hour, 1,000 a day; for personal use |
   | Mutual funds | **Tiingo** | free | daily NAVs, posted around midnight Eastern |
   | Fallback for both | **Alpha Vantage** | free | 25 requests a day, so only when Tiingo fails |
   | Money-market funds | none | — | held at $1.00, shown as such |
   | Crypto, major coins | **Coinbase** public prices | none | |
   | Crypto, other coins | **CoinGecko** Demo plan | free | about 10,000 calls a month; attribution required, shown in Settings and on charts that use it |
   | Gold spot | **PAXG** (a token backed by one troy ounce of gold), from Coinbase | none | tracks spot closely; a proxy |
   | Silver, platinum and palladium spot | **SLV**, **PPLT** and **PALL** from Tiingo, divided by each fund's metal per share | free | the metal per share ships with the tax tables (S16.11) and is updated with them; within a fraction of a percent of spot |
   | Options | **Massive** (formerly Polygon.io), Basic plan | free | end-of-day prices and two years of history; 5 calls a minute, each page of a result counting as one |
   | Treasuries, I bonds and EE bonds | computed | — | from the Treasury's published yield curve and savings-bond rates, which are free official data |
   | No free ticker: 529 portfolios, 401(k) collective trusts, individual corporate and municipal bonds | **manual** | — | a value from a statement or an import, or a typed price, with its date. A statement value older than 90 days is marked stale and raises an alert (S12.11) |

4. **Schedule**: once a day, after the US market close (6:00 PM Eastern by default), a
   background task loads the day's close for every **held or watched** instrument, and
   backfills history when an instrument is first held. **Refresh prices** does the same on
   demand. Requests are spread to stay inside each source's limits (Tiingo's 50 an hour
   means a few hours for a large household). A source that fails falls back to the next one
   for that class; Settings shows the last error, and a failure lasting past the alert
   threshold raises an alert (S12.11). Intraday quotes are not fetched.
5. **Option marks**: the day's close from the source that serves options, else manual or
   intrinsic value (S3.7). A close older than the last trading day is marked stale.
   Massive is asked for an option by its OCC ticker (`O:MSFT261120P00480000`: underlying,
   expiry, put or call, and the strike in thousandths). A typed mark is a price on the
   option's instrument, entered from the open position (**Type a mark**). Intrinsic value is
   the underlying's latest close past the strike, never below zero. The Open tab labels a
   mark that is typed or intrinsic. Greeks
   are out of scope ([out of scope](out-of-scope.md)).
6. **Stored prices** are kept: daily closes for ever.
   Charts read stored prices only, never a price source during a request.
7. **Every price carries its source and `as_of`.** The UI shows *delayed* or *as of 4:00 PM*
   on every value derived from it. A price older than a threshold (2 trading days for a
   stock) is marked stale.
8. **US dollars only**: every account, holding, price and total is in USD. Prices are fetched
   in USD, including crypto and metals spot. An instrument that trades only in another
   currency is priced by hand.
9. **Linked servers never call price sources for each other.** A peer's shared data carries its
   own values and their `as_of` (S11.5).
