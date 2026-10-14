# S1. Accounts

1. **Account types**, each with its own icon and hue:

   | Type | Group | Holds | Tax treatment |
   | --- | --- | --- | --- |
   | `checking`, `savings`, `money-market`, `cd` | Banking | cash | taxable (interest) |
   | `credit-card` | Liabilities | a negative balance | — |
   | `mortgage`, `heloc`, `auto-loan`, `student-loan`, `personal-loan`, `loan` (any other) | Liabilities | a loan with terms (S1.9) | mortgage and student-loan interest may be deductible |
   | `brokerage` | Investing | cash, stocks, ETFs, funds, bonds, options | taxable |
   | `ira` (traditional, SEP, SIMPLE) | Retirement | as brokerage | tax-deferred |
   | `roth-ira` | Retirement | as brokerage | tax-free (qualified) |
   | `401k`, `403b`, `457b` (traditional and Roth parts) | Retirement | funds, cash | tax-deferred / tax-free |
   | `hsa` | Retirement | cash, funds | triple tax-advantaged |
   | `529` (college savings) | Education | funds, cash, for one beneficiary (S1.8) | tax-free for qualified education |
   | `daf` (donor-advised fund) | Giving | funds, cash | deducted when contributed; grants are not deductible again (S7.9) |
   | `crypto-exchange` | Crypto | coins, fiat cash | taxable |
   | `crypto-wallet` (self-custody) | Crypto | bitcoin | taxable |
   | `precious-metals`, `collectables`, `real-estate`, `vehicle`, `other-asset` | Physical assets | items, each with its own basis and value (S1.10) | gains on collectables and metals: the collectables rate |

   A `daf` counts in no one's net worth by default: its money is already given away.
   **Count in net worth** on the account overrides that.

2. **Every account has** a name, its type, the institution, an optional masked number (last
   4), its owner, an **active** switch (a closed account stays
   for history and taxes), notes, and how it is kept current (S1.3).
3. **How an account is kept current**, one or more of:
   1. **manual**: transactions and balance snapshots typed in;
   2. **file import**: **OFX and QFX** files (the structured downloads most US banks and
      brokers offer; brokers' files also carry positions and trades), read with ofxtools;
      CSV, with a saved column mapping per institution; and brokers' and exchanges'
      trade-history CSVs. Imports are idempotent: a re-imported file adds only what is new,
      matched by the file's transaction id (an OFX file's `FITID`) or by date, amount and
      payee;
   3. **statement import**: a **PDF statement**, read from its text layer, or a **photo or
      scan** of one, read with RapidOCR as receipts are (S9.8), all on the server. MoneyKata
      finds the statement's period, its transactions and its opening and closing balances,
      and shows them for the user to check and correct before anything is saved. The
      transactions must add up from the opening to the closing balance; where they don't,
      the difference is shown and nothing is saved until it is resolved or accepted. What it
      learns about an institution's layout is kept per institution, so the next statement
      needs fewer corrections. Imports are idempotent here too. The statement file is kept as
      a receipt attached to the account (S9);
      1. **What it reads**: bank and card statements of one account, any number of pages, as
         UMB, Schwab Bank and card issuers lay them out. The period comes from a *Statement
         Period* or *Opening/Closing Date* line (else the first and last transaction); the
         balances from *Beginning/Opening/Previous* and *Ending/Closing/New Balance*; a
         transaction is a line that starts with a date and ends in amounts. Its sign comes
         from the running balance where there is one, else from an explicit sign (`-`,
         `( )`, `CR`), else from the section it is in (*Deposits and Other Credits*,
         *Withdrawals*, *Checks Paid*, *Purchases*, *Payments and Credits*), else from its
         words, and is then marked as guessed. Summary and daily-balance sections are left
         out. A card statement's figures are what is owed, and are turned to the account's
         side.
      2. **Reading** uses the receipt reader's worker (S9.8.4): a text layer when the PDF has
         one, else OCR. Settings › Imports can turn statement reading off.
      3. **Checking**: the period, both balances and each line can be corrected, and a line
         left out; lines already in the account start left out. The opening balance becomes
         the account's reported balance the day before the period, the closing balance its
         balance on the last day (S1.11).
      4. **What is learned per institution** (per owner): the sign of each section heading the
         person kept, and the first words of lines they left out, which are skipped next
         time. Brokerage statements and statements of several accounts are G8.
   4. **bitcoin watch** (self-custody wallets): balances and transactions read by address or
      xpub (S1.6).

   No bank-aggregation service is used: the user brings the files ([rejected ideas](rejected-ideas.md)).
4. **Retirement accounts** also carry: the **contribution year** of each contribution (a
   contribution made 2027-03-01 may be for 2026), employer match and vesting for a 401(k), and
   the account holder's **birth year** (from the profile) for limits and RMDs. Contribution
   limits per year are a table shipped with the app and updated with it, which an admin can
   correct in Settings (S8.6).
5. **Crypto exchanges** (Coinbase, Kraken and the like) are kept current from their CSV
   exports and statements, one import mapping per exchange. Reading an exchange through its
   API comes later ([out of scope](out-of-scope.md)).
6. **Self-custody wallets** hold **bitcoin**. Other coins and chains come later ([out of scope](out-of-scope.md)).
   1. **What the account holds**: addresses, or an **xpub/ypub/zpub** from which addresses
      are derived (with a gap limit of 20 unused addresses by default).
      1. An xpub's addresses are legacy (1…), a ypub's nested segwit (3…) and a zpub's
         native segwit (bc1q…), on the receive chain (0/i) and the change chain (1/i).
         Addresses typed are checked: legacy, script (3…), native segwit and taproot (bc1p…).
         Mainnet only: a testnet key or address is refused.
      2. Each chain is derived until the gap limit (1 to 200) of addresses in a row past the
         last used one are unused; when the explorer or node finds one used, more are
         derived. The account's Settings lists the addresses watched, by chain and index.
      3. Taking a key or address out of the list stops watching its addresses.
   2. **Where balances and history come from**, set by an admin in Settings › Bitcoin:
      1. a **public explorer** with the Esplora API (mempool.space by default, or
         Blockstream);
      2. **the household's own node**: its own mempool or Esplora instance, an **Electrum
         server** (Fulcrum, electrs), or **Bitcoin Core** over RPC with a watch-only
         descriptor wallet. An own node keeps the household's addresses private, and is
         recommended. Its address is named by the admin, so the egress guard (S13.5) lets
         MoneyKata reach it on the LAN; its credentials are a secret (S14.4).
   3. The form **refuses anything that looks like a private key or seed phrase** (WIF, 64
      hex digits, 12 or 24 BIP-39 words, an extended private key such as an xprv), says why,
      and never stores or logs it. The browser clears it from the form as it is typed, before
      anything is sent; the server checks again and its refusal never repeats it.
7. **Transfers** between two of a user's accounts are matched (same amount, a few days apart),
   so they count neither as spending nor as income, nor as a buy or sell of cash.
8. **529 plans.** A `529` account holds funds and cash like a brokerage account, plus:
   1. **The plan**: its state and name, the **beneficiary** (a person, S7.7, or a user), the
      opening date, and the state tax deduction the owner expects per year (typed: state
      rules are not modelled, S8.18).
   2. **Contributions** record who contributed (the owner, or a named relative), so gifts to
      the beneficiary can be totalled per contributor per year against the **annual gift
      exclusion** (in the tax tables, S16.11). A **five-year election** (superfunding)
      spreads one contribution over five years of exclusions and is shown that way.
   3. **Withdrawals** are matched with **qualified expenses** (tuition and fees, room and
      board, books, a computer, K-12 tuition, apprenticeships, student-loan repayment), each
      with its receipts (S9). Each year shows distributions (from Form 1099-Q) against the
      qualified expenses, and the part not covered, whose earnings may be taxable (S8.10).
   4. **Rollover to a Roth IRA**: once the account has been open 15 years, it shows how much
      could still roll over to the beneficiary's Roth IRA under the lifetime limit (in the
      tax tables), excluding contributions of the last five years.
   5. **The Goal tab** shows the beneficiary's education projection (S6.2.2).
   6. A 529 counts in its **owner's** net worth, not the beneficiary's.
9. **Loans and mortgages.** A loan account carries its **terms**:
   1. **Terms**: the original principal, the start date, the term (months), the interest
      rate, fixed or adjustable (an ARM's adjustment dates, caps and the rate after each
      reset, typed when known), the interest method (monthly amortization, or simple
      interest accrued daily, as most car loans use), the scheduled payment, and for a
      mortgage **escrow** (property tax, insurance) and **PMI**. A HELOC has a draw period
      with interest-only payments, then a repayment period.
   2. **The amortization schedule** is computed from the terms: each payment's interest,
      principal, escrow and remaining balance. It is recomputed when a payment differs
      from the schedule, the rate resets, or the loan is **recast**.
   3. **Payments**: a payment transaction from a bank account (matched as a transfer, S1.7) is
      **split** into principal, interest, escrow, PMI and fees by the schedule. The user can
      correct a split from the servicer's statement. Principal beyond the schedule is
      recorded as an **overpayment**. Bank transactions of the last 90 days within 2% of the
      payment, not yet a transfer and not filed under another category, are offered on the
      loan's screen to link as its payments.
   4. **Reconciling**: the servicer's statement balance can be typed in on a date, and a
      difference from the computed balance is shown until it is explained (a fee, a missed
      payment, a wrong rate).
   5. **The loan's screen** shows the balance, the rate, the payoff date, interest paid to
      date and still to pay, principal paid this year, the schedule, and the **payoff
      planner** (S6.10). A mortgage linked to a `real-estate` item shows the **equity** and the
      **loan-to-value**, and when PMI can be dropped (on request at 80% of the original
      value; automatically at 78%).
   6. **Taxes**: mortgage interest, points and PMI (Form 1098), and student-loan interest
      (Form 1098-E) appear in Taxes (S8.12).
10. **Physical assets.** A physical-asset account (`precious-metals`, `collectables`,
    `real-estate`, `vehicle`, `other-asset`) holds **items**:
    1. **Every item has** a name, a category, a description, the **date acquired**, how it
       was acquired (bought, a gift, inherited), the **cost basis** (price plus premium,
       fees, shipping and improvements; a gift's carried-over basis; an inherited item's
       value at death), the quantity, where it is kept, a serial or certificate number, its
       condition or grade, the insured value and policy, **notes** (Markdown), and photos
       and documents (purchase receipt, appraisal, certificate, title), stored as receipts
       (S9).
    2. **Valuation**, one of:
       1. **spot**, for precious metals: the item's **fine weight** (weight per unit, in troy
          ounces, grams or kilograms, times purity, such as .9999, .925 or 22k, times
          quantity) times the metal's spot price (S4.3), adjusted by the premium or discount
          the user expects when selling (0% by default);
       2. **valuations**: dated values with their source (appraisal, recent sale, price
          guide, estimate), the latest one counting. A valuation older than 12 months is
          marked stale;
       3. **depreciation**, for vehicles: a yearly percentage from the purchase price, until a
          valuation replaces it.
    3. **Precious metals** are summarised by metal (gold, silver, platinum, palladium): fine
       ounces held, average cost per ounce, value at spot, and gain. Forms: coin, bar, round
       and jewellery. A numismatic coin worth more than its metal is a collectable instead.
    4. **Real estate** keeps the address (optional), purchase price and closing costs,
       **improvements** (each added to the basis with its receipts), valuations, whether it
       is the **primary residence**, and the loans secured by it (S1.9.5).
    5. **Selling** an item records the date, proceeds and fees, and realizes a gain or loss,
       flagged on Form 8949 as a **collectable** where it is one (metals included), which the
       tax tables tax at the collectables rate. A loss on personal-use property (a car, a
       home) is shown as not deductible (S8.13).
    6. **An account's chart** is its items' total value over time. The Items tab lists the
       items with cost basis, value, gain and age, and opens each one with its history,
       notes and documents.
11. **Reconciliation** keeps an account's balance in step with the institution's, for banking,
    card, brokerage-cash and loan accounts. For a user who only imports files it is a set of
    quiet, automatic checks; ticking off transactions by hand is an option.
    1. **Coverage**: each import records the dates it covers. The account's *Reconcile* tab
       shows a timeline of covered and uncovered periods, and flags a **gap** (*nothing
       between Aug 3 and Aug 14*) and an **overlap**.
    2. **Balance anchors**: a balance the institution reported, on a date, from (in order of
       preference) a CSV's **running-balance column** (every row is then an anchor), an
       OFX file's ledger balance, a statement's closing balance (S1.3.3), or a balance the
       user **types** from the institution's site. When an account has had no anchor for 45
       days, it asks for one.
    3. **The check**: at each anchor, MoneyKata's balance for that day is compared with the
       anchor. A match stays quiet. A **mismatch** shows the difference, the window between
       the last matching anchor and this one, and what is suspect inside it: likely
       duplicates, amounts that changed between imports, and coverage gaps. With a
       running-balance column, it names the first row where the balances part.
    4. **Resolving** a mismatch: import the missing file, remove a duplicate, correct a
       transaction, or accept the difference as a **balance adjustment** with a note, which
       shows as such in the account and in Activity. An account with an open mismatch is
       marked in Accounts, and raises an alert after 7 days (S12.11).
    5. **Duplicate suspects** are flagged, never merged silently: two identical rows on one
       day ask *both real?* the first time, and the answer is kept.
    6. **Ticking off** (optional, for accounts kept by hand): pick a statement's closing date
       and balance, tick transactions as cleared until the difference is zero, and the period
       is marked **reconciled**. Editing a transaction inside a reconciled period asks first.
