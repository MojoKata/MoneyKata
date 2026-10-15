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
5. **Strategies**: legs held together (a covered call, a vertical spread, an iron condor)
   are grouped and shown as one. Grouping is a label: lots, gains, wash sales and taxes stay
   per leg.
   1. **Grouping is proposed, never forced.** Legs on one underlying opened in one account on
      the same day are offered as a strategy on the Positions screen (*Group as an iron
      condor?*), and a short call against 100 or more shares held, whenever they were
      bought, as a covered call. Legs can be grouped by hand (select them, **Group**) and a
      group undone at any time.
   2. **Rolls**: a leg closed and another opened on the same underlying the same day is
      offered to stay in the group. A strategy keeps its history (its legs, its rolls and
      its P/L from open to close, closed legs included).
   3. **The shapes recognised** (anything else is *Custom*): long call, long put, short call
      (naked), short put (*cash-secured* is the owner's tick); covered call, protective put,
      collar; bull and bear call spreads and put spreads; long and short straddles and
      strangles; iron condor, iron butterfly, butterfly; calendar and diagonal.
   4. **Figures**: cost or credit, mark, unrealized and realized P/L, **max profit**, **max
      loss** and **breakevens at expiry**, *unlimited* where it is. A calendar or diagonal
      shows its P/L only, as its outcome depends on volatility.
   5. **Capital at risk**, shown **now** and **at open**:

      | Strategy | Capital at risk |
      |---|---|
      | long options, debit spreads | the net premium paid |
      | credit spreads, iron condor and butterfly | the widest wing × multiplier × contracts, less the net credit |
      | cash-secured put | strike × multiplier × contracts, less the premium |
      | covered call, protective put, collar | the shares' market value, less the net premium |
      | naked call, short straddle and strangle | *unlimited*, or the broker's margin requirement the owner types |

      *Now* uses today's prices; *at open* uses those of the day the strategy opened, and
      is what a strategy's **return on capital at risk** is worked on. The shares' cost basis
      shows on their own leg.
   6. **Where it shows**: Positions lists legs under their strategy, expandable, with these
      figures; an investing account and a portfolio show **Capital at risk** beside their
      options' market value. Allocation charts keep market value.
6. **Expiry** is applied automatically the day after an option expires out of the money by
   the underlying's closing price. An in-the-money expiry asks the user what happened.
7. **Valuation**: an open option's mark is the price source's daily option close where there is
   one (S4.5), otherwise the user's manual mark, otherwise intrinsic value, labelled as such.
8. **Wash sales**: a loss sale with a purchase of the same or a *substantially identical*
   instrument within 30 days either side is flagged, its disallowed loss computed and added to
   the replacement lot's basis. This covers the user's own accounts, IRAs included, and the
   accounts of the user's spouse on the date of the sale (S10.10.4). Options on the same
   underlying are flagged for review, not decided (S8.3).
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
   5. **Flagged for review, never adjusted**: where the rules are unsettled or depend on
      facts MoneyKata can't see, a possible wash sale is listed among the tax book's issues
      (S8.3) with the trades involved, and no basis is changed:
      1. a loss on a **short sale** closed with shares bought within 30 days of another
         short sale of the same stock, or of opening one;
      2. a loss on an **option itself** (a call or put closed or expired at a loss) with the
         same option, or one on the same underlying, opened within 30 days either side;
      3. a loss on stock whose **replacement came through an option**: a put assigned to the
         user, or a call they exercised, within 30 days either side of the loss sale;
      4. a loss on stock with an **option on it bought or sold** within 30 days either side.

      The issue names the rule it may fall under and says the preparer decides.
9. **Gain/loss views**: realized by year, month, account, instrument and short- or long-term;
   unrealized now; and **per trade** for options (open date, close date, premium in and out,
   P/L, return on capital at risk).
   1. An option trade runs from the first contract opened in an account to the moment none
      is open. Premium in and out are the cash received and paid, fees included; a trade
      still open adds what it is worth at its current mark, as *if closed now*.
   2. **Capital at risk**: for a long option, the premium paid; for a short one, the strike
      on every share the most contracts open at once cover (the cash to buy them for a put,
      the shares to deliver for a call). The return is the P/L over it. A leg in a strategy
      takes its strategy's capital at risk at open instead (S3.5.5).
10. **Adjusted contracts**: when the underlying splits, merges, spins off a company or pays a
    large special dividend, the OCC adjusts its open options. The lot carries over to the
    adjusted contract: no sale, and no wash sale.
    1. **A whole-number split** (2:1, 4:1) is applied with the stock's split (S2.4):
       contracts × the ratio, strike ÷ the ratio, the basis spread over the new contracts.
       The old contract ends.
    2. **Any other adjustment** gives the contract a new root (AAPL becomes *AAPL1*), keeps
       its strike, and changes its **deliverable**: shares other than 100 (150 for a 3:2
       split), shares and cash, or shares of two companies. Recording the corporate action
       asks for each open contract's new root, strike and deliverable, from the OCC's
       information memo (linked to its search).
    3. **On import**, a line whose symbol has an adjusted root (one ending in a digit) is
       offered to link to the open contract it adjusts.
    4. **Assignment and exercise** of an adjusted contract open or close a lot for each
       instrument in its deliverable, and its cash goes into the proceeds or the basis.
    5. **Its mark** is CBOE's, which lists it under its new root in the underlying's chain
       (S4.5); without one, its intrinsic value is its deliverable's value less the strike
       × 100.
