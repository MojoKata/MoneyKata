# S3. Positions and options

1. **A position** is one instrument in one account. It is **open** while any lot is open,
   and **closed** when none is. The Positions screen lists open and closed positions with
   quantity, average cost, market value, unrealized gain or loss (amount and %), realized gain
   or loss, days held, and short- or long-term status per lot.
2. **Option transactions:** *buy to open*, *sell to open*, *buy to close*, *sell to close*,
   **expire** (worthless), **assigned** and **exercised**. Each carries contracts, premium per
   share, fees and commission.
3. **Short options** are negative lots. The premium received is the credit; the gain is
   realized at close or expiry.
4. **Assignment and exercise** close the option lot and open or close stock lots at the
   strike, with the premium folded into the stock's basis or proceeds as the IRS rules for
   that case say: a long call exercised adds its premium to the stock's basis, a short put
   assigned subtracts its premium from it, a short call assigned adds its premium to the
   proceeds. The resulting stock lots link back to the option.
5. **Strategies** *(optional, later)*: positions opened together (a covered call, a vertical
   spread, an iron condor) can be grouped and shown with their combined P/L, max profit and
   loss, and breakevens. Grouping is a label. The lots and gains stay per leg.
6. **Expiry** is applied automatically the day after an option expires out of the money by
   the underlying's closing price. An in-the-money expiry asks the user what happened.
7. **Valuation**: an open option's mark is the price source's daily option close where there is
   one (S4.5), otherwise the user's manual mark, otherwise intrinsic value, labelled as such.
8. **Wash sales**: a loss sale with a purchase of the same or a *substantially identical*
   instrument within 30 days either side is flagged, its disallowed loss computed and added to
   the replacement lot's basis. This covers the user's own accounts, IRAs included, and the
   accounts of anyone the user marks as their spouse. Options on the same underlying are
   flagged for review, not decided (S8.3).
9. **Gain/loss views**: realized by year, month, account, instrument and short- or long-term;
   unrealized now; and **per trade** for options (open date, close date, premium in and out,
   P/L, return on capital at risk).
