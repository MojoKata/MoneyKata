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
   1. The match is the same instrument, a stock or fund (ETFs and mutual funds included),
      bought or reinvested within 30 days before or after a sale at a loss in a taxable
      account. Whether a different instrument is substantially identical is the preparer's
      call, and MoneyKata does not guess.
   2. Replacement shares are taken nearest the sale date first, each counted against one
      sale only. The shares bought in the lot that was sold are never their own replacement.
      A partial replacement disallows the loss in proportion: 4 shares bought back of 10
      sold disallow 4/10 of the loss.
   3. The disallowed loss is taken off the sale's realized loss and added to the replacement
      shares' basis, and their holding period starts that many days earlier: the sold
      shares' days held carry over. Holdings, unrealized gain, the Closed tab (a **W** with
      the amount) and the later sale of those shares all use the adjusted basis and date.
      Where only some of a lot replaces, that part is split into its own lot.
   4. The household's wash sales are worked out again whenever a trade in it is added,
      changed, deleted or imported, so a later purchase that replaces an earlier loss, or a
      deleted one that no longer does, takes effect at once.
9. **Gain/loss views**: realized by year, month, account, instrument and short- or long-term;
   unrealized now; and **per trade** for options (open date, close date, premium in and out,
   P/L, return on capital at risk).
   1. An option trade runs from the first contract opened in an account to the moment none
      is open. Premium in and out are the cash received and paid, fees included; a trade
      still open adds what it is worth at its current mark, as *if closed now*.
   2. **Capital at risk**: for a long option, the premium paid; for a short one, the strike
      on every share the most contracts open at once cover (the cash to buy them for a put,
      the shares to deliver for a call). The return is the P/L over it.
