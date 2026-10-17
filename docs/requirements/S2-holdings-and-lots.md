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
7. **Categorisation rules**, which are also the **payee rules** of S2.6: an ordered list per
   user, in **Transactions › Rules**, first match wins.
   1. **What a rule matches**: the payee as the institution wrote it, by text it contains (case
      aside) or, after `re:`, a regular expression (Python's, case aside, at most 200
      characters; a nested repeat such as `(a+)+` is refused, as it can take a payee
      forever); and, when given, an amount range (from and to, of the amount without its
      sign), a direction (money in, money out, or either) and one account.
   2. **What it sets**, one or more of: the **category**; the **payee** shown (*Rename to*),
      the institution's text kept beside it; and **tags**, the user's own (S2.6).
   3. **On import** (a file, a statement or a connector's fetch), the rules of the user who
      imports are applied to each new row that is a bank transaction (not a trade) and not a
      transfer between the owner's accounts (S1.7). A row's category is set only when it has
      none, and a split is never touched.
   4. **On demand**, *Apply to the uncategorised* runs the user's rules over the uncategorised
      transactions in the accounts they can change, and says how many it set; Activity records
      that count, never an amount (S10.8).
   5. **The list** shows each rule's conditions and what it sets, and can add, edit, delete and
      move a rule up or down; each change is recorded in Activity as a rule change. A rule
      whose account or category was deleted shows it as deleted; one whose account went
      matches nothing. Rules are their user's own: never shared, and never across a link
      (S11.5.2).
   6. **From a transaction**: its dialog offers *Make a rule*, with its payee and category
      filled in.
   7. **The receipt reader** passes the merchant it read through the uploader's rules: a rule
      that renames a payee renames the merchant the same way (S9.8.2.5.3).
8. **Editing history** is allowed. Every derived figure (balances, lots, gains, budgets,
   charts) follows on the next request. An edit that changes a closed tax year's realized
   gains asks for confirmation first.
