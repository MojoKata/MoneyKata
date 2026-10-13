# MoneyKata: requirements

Status: **DRAFT** 2026-10-10. MoneyKata is a self-hosted **personal finance server** for a
household or a small group of people. It holds their accounts (bank, brokerage, crypto
exchange, self-custody wallets, IRA, Roth IRA, 401(k)), tracks holdings and positions (options
included), charts portfolios, projects future value, keeps budgets and receipts, and prepares
the numbers a tax return needs. Several people use one server. They share accounts and
portfolios with each other, read-only or read/write, and share read-only with people on
**other MoneyKata servers** on other LANs.

§3 states the design's principles, §20 the technical stack, §21 the open questions, §22 the
gaps still to design, and §23 what is out of scope.

**Mockup:** [`mockups/MoneyKata-mock.html`](mockups/MoneyKata-mock.html) is the clickable
mockup. It is one file that opens from disk and sends nothing anywhere. For now it is
hand-written. Once `web/ui` exists, it is generated from the app (§15.9). Its
purple **MOCK** pill jumps to any screen, switches between users, and opens the dialogs.

# 1. Decisions

The rulings the rest of this document applies. Rulings marked *(proposed)* are
recommendations waiting for a decision.

1. **The stack** (§20): a Python server (FastAPI under Hypercorn), SQLite through
   **SQLAlchemy** with **Alembic** migrations, and a browser app with **no build step** (Preact,
   HTM, @preact/signals, preact-iso, vendored and pinned, loaded as plain ES modules under a
   strict CSP). There is **no Node.js anywhere**. Deno type-checks and lints, and Playwright for
   Python runs the browser tests.
2. **A single-page app at `/ui`**, dark-mode first, in one frame: a collapsible
   sidebar, the signed-in user at its foot, the theme button, a DEV pill in dev mode and an
   update pill. It is built for desktop browsers. Phones will get a separate, focused PWA
   later, not the whole web app (§15.8, §23).
3. **Context-sensitive help on every screen**: the F1 help pane, with one Markdown guide per
   screen or panel that follows the focused field (§15.7). A test fails when a field has
   no heading in its guide.
4. **A clickable mockup** in `docs/mockups/`, opened from disk. It shows every screen and
   dialog on sample data, and its MOCK pill drives it (§15.9).
5. **A dev mode, `moneykata dev`**, runs the whole server from a checkout as the current user.
   It uses a self-signed certificate, writes emails to a folder, uses canned price feeds and
   seed data, and keeps every rule as strict as production (§20.7).
6. **Users, groups, invitations, sign-up approval, two-step sign-in and deactivation**
   (§13.1). An admin's extra powers are managing users and groups and the server's
   Settings. **Admins cannot see other users' money** unless it is shared with them (§13.2).
7. **Users own accounts.** Any user can create accounts and portfolios and share them with
   users or groups, **read** or **read/write** (§13).
8. **Linked servers.** Two MoneyKata servers on different LANs can be linked. A link carries
   **read-only** shares of accounts and portfolios one way, and is never read/write (§14).
9. **Money is never a float.** Amounts and quantities are decimals end to end: `Decimal` in
   Python, strings in JSON, and integers or decimal text in SQLite (§17.3).
10. **Prices are delayed, never live.** MoneyKata is not a trading app. It reads end-of-day
    closes from free sources, through pluggable **price sources** (§7).
11. **Read-only by construction toward institutions.** MoneyKata never moves money, places an
    order or signs a transaction. It never stores a self-custody wallet's private key or seed
    phrase, only public addresses or extended public keys (§4.6).
12. **Receipts are files on the server**, PDF or image, uploaded from the browser and attached
    to transactions, tax items or nothing (§12).
13. **Everything the server stores is encrypted at rest**: the database
    (SQLCipher), the receipt files, and each secret on its own. All of it opens with one
    **master key**, kept in a file on the host outside the database and its backups, and
    backed up as a **12-word recovery phrase** (§18). The server's own account reads the key
    file. There is no separate keys process, and **no Vault or other external key service**
    (§18.2).
14. **Charts: Apache ECharts**, vendored and loaded only by the screens that draw charts
    (§20.4).
15. **The code lives in `web/`**: `web/ui` (the browser app) and `web/server` (the Python
    package `moneykata`). The docs are in `docs/` (§20.1).
16. **MoneyKata informs and does not advise.** Tax reports, projections and gain/loss figures
    are worksheets for the user or their preparer. They are not tax, legal or investment
    advice, and the screens say so where it matters (§11.18).
17. **Receipts are read on the server with RapidOCR**: open source, CPU
    only, models shipped with the app, run as a sandboxed background job. Results are
    suggestions the user confirms (§12.8).
18. **What a link brings in is kept apart and encrypted**. Each link's shared data lives in its own **linked copy**: a SQLCipher
    database plus one encrypted file per receipt, in a folder of its own, never in the main
    database. It opens with the copy's own **access key**, 12 generated words that the
    receiving household keeps in its password manager, never with the master key. The key
    protects the copy at rest; who sees what is decided by the owner's shares. The copy
    keeps syncing while it is locked, and its key is released after an hour unused (§14.9).
19. **Beyond investments**: MoneyKata also covers **529 plans** (§4.8),
    **mortgages and other loans** with payoff and overpayment projections (§4.9, §9.10),
    **physical assets** such as precious metals, collectables, property and vehicles, with
    notes, purchase dates and cost basis (§4.10), **gifts** to the people in a user's life
    for their birthdays, anniversaries and holidays (§10.7, §10.8), and **charitable giving**
    against a target set as a percentage of income (§10.9).
20. **Schema conventions**: tables are declared with SQLAlchemy Core,
    with no logic beside them, and mapped onto plain dataclasses (§17.1). Table names are
    singular and capitalized, field names camelCase, and primary keys a short prefix plus a
    Crockford-encoded UUIDv7, such as `User_01k7ab4vstfggspkjt3my8wzr2`.
    [`schema.md`](schema.md) holds the conventions and the list of prefixes.
21. **Taxes are kept in tax books**: one per user, or married couple,
    and year. A tax book holds the documents received and one **filing** per return
    (federal, state, local), each with the forms as filed, the tax authority's letters and
    any amendment. Another user can be given write access to help prepare it (§11.14).
    MoneyKata still prepares worksheets only and never files.
22. **Owners choose people on other servers**. Linked servers exchange
    their lists of active users, so an owner shares any of the seven shareable kinds (account,
    portfolio, budget, person, giving plan, tax book, projection) with named people on another server,
    as they do with people on their own (§13.3). What a household shares is shown in a
    **window of its own**, never mixed with this household's data (§15.10). This suits
    household servers; a server for more than a household would need users to opt in to
    being listed (§23).
23. **US dollars only.** Every account, price, total and report is in USD. There are no
    foreign accounts and no currency conversion (§7.8, §23).
24. **Records are soft-deleted.** Deleting marks a record deleted, with when and by whom, and
    a view per table works out whether it is deleted through what it belongs to. The few
    exceptions are listed in [`schema.md`](schema.md) (§17.1.5).
25. **Alerts** tell people when something needs them, above all admins when a source has
    failed for more than 48 hours. They show as a live count on the **Alerts** screen, and
    each user chooses to be emailed each one, a daily summary, or nothing (§15.11).
26. **Account data comes from files the user brings.** Bank, card, brokerage and exchange
    accounts are kept current from files: OFX/QFX and CSV downloads, PDF statements, and
    photos of statements read on the server. There is no bank-aggregation service (§4.3,
    §24). **Bitcoin** is the one chain watched, through a public explorer or the household's
    own node; other coins and exchanges' APIs come later (§4.5, §4.6).

# 2. Terminology

1. **Institution:** a bank, broker, exchange, plan administrator or blockchain that holds the
   money. It is a label on an account, not an entity with credentials.
2. **Account:** one place money is held, owned by one user: a checking account, a brokerage
   account, a Roth IRA, a Coinbase account, a Bitcoin wallet. Every account has an **account
   type** (§4.1) that decides its fields, tax treatment and screens.
3. **Holding:** what an account holds of one **instrument** (cash, a stock, a fund, a coin, an
   option contract) at a point in time: its quantity, cost basis and value.
4. **Instrument:** a thing with a price, such as `AAPL`, `VTI`, `BTC`, or `AAPL 2026-12-18
   250 C`. Cash is an instrument with a price of $1.
5. **Lot:** one acquisition of an instrument: date, quantity, cost, and what remains open.
   Gains, holding periods and wash sales are computed per lot.
6. **Transaction:** one dated movement in an account: deposit, withdrawal, purchase, sale,
   dividend, interest, fee, transfer, option open, close, expiry, assignment or exercise. A
   bank transaction has a payee and a budget **category**.
7. **Position:** an instrument held in an account, followed from **open** to **closed**, with
   its realized and unrealized gain or loss. Options are positions (§6).
8. **Portfolio:** a named set of accounts, or of a part of them (§8), owned by one user and
   charted as one. *All my accounts* is everyone's implicit first portfolio.
9. **Share:** a grant of one account or portfolio to a user, a group or a linked server, at a
   **level**: `read` or `write` (§13). A share to a linked server is always `read`.
10. **Linked server (peer):** another MoneyKata server this one has a **link** with (§14).
    What a link brings in is kept in that link's **linked copy**, encrypted under its own
    **access key**: 12 generated words that the receiving household keeps. The copy is
    **locked** until someone it shares with enters the words, and locks again after an hour
    unused. It is shown in its own **linked household** window (§14.9, §15.10).
11. **Price source:** an integration (a `TickerSource`) that supplies daily prices for one
    or more instrument classes (§7).
12. **Projection:** how money will grow toward a goal (retirement, education or a savings
    target), from contributions, returns and withdrawals over time. An **active** projection
    is the plan being followed, tracked against its baseline (§9).
13. **Budget:** a period's planned amounts per category, compared with the actual
    transactions (§10).
14. **Receipt:** an uploaded file (PDF, JPEG, PNG, HEIC, WebP) with a date, an amount and
    links to what it supports (§12).
15. **Tax book:** the tax records of one user, or of a married couple filing jointly, for one
    **tax year** (a calendar year): the tax documents they received (W-2s, 1099s), and a
    **filing** per return (federal, state or local) with the forms as filed and what the tax
    authority sent back (§11.14–11.17). The Taxes screen shows one tax book at a time.
16. **Loan:** a liability account with terms (principal, rate, term, payment) from which
    MoneyKata computes an **amortization schedule**. A **mortgage** is a loan secured by a
    property. An **overpayment** is principal paid beyond the schedule (§4.9).
17. **Physical asset:** a thing of value that is not a security: precious metals,
    collectables, property, a vehicle. A physical-asset account holds **items**, each with
    its own purchase date, cost basis, valuations and notes (§4.10).
18. **Person:** someone in a user's life who is not necessarily a user of the server: a
    child, a parent, a friend. A person has dates (**occasions**) such as a birthday or an
    anniversary, and can be a 529 plan's beneficiary (§10.7).
19. **Gift:** something given to (or received from) a person for an occasion, from idea to
    given, with its cost (§10.8). **Giving** means charitable donations, tracked against a
    **giving target** (§10.9).
20. **Words not used:** *Wallet* for anything but a self-custody crypto wallet. *Asset* on
    its own for a security: the UI says holding or instrument, and keeps *asset* for
    *physical asset* (term 17). *Trade* as an entity: a trade is a pair of
    transactions on a position.

# 3. Design principles

1. **One server, on the household's own LAN.** All data stays on hardware its users control.
   The only outbound calls are to price sources, the bitcoin explorer or node, and linked
   servers that a user or admin set up, and each is visible in Settings (§19).
2. **The ledger is the truth.** Holdings, balances, positions, gains and charts are derived
   from transactions and lots. A **balance snapshot** may stand in for history where none is
   available, such as an opening balance or a 401(k) statement, and it is marked as such.
3. **Exact arithmetic.** Decimals everywhere, with rounding only at display or where the tax
   rules say to round (§17.3).
4. **Least privilege in sharing.** A share grants one account or portfolio, at one level, to
   whom it names. It is never re-shared. Revoking it ends access on the next request.
5. **Safe defaults.** A new account is shared with no one. A new link carries nothing until
   something is shared with it. Price sources and the bitcoin explorer are off until
   configured.
6. **Never hold the keys to the money.** There are no private keys, seed phrases or trading
   permissions, and no credentials for a bank or an exchange.
7. **One store, live on the next request.** There are no caches between the database and a
   request, so a change (a share revoked, a rule edited) applies to the very next one. A record
   is validated as a whole when saved, every change is saved explicitly, and a refusal names
   the field and the reason, which the UI shows at that field.
8. **Audit names fields, never values.** Activity says "Alice changed the
   category of 3 transactions", and amounts stay out of the log.
9. **The contract is generated.** OpenAPI comes from the routes, the UI's JSDoc types come
   from it, and a check fails on drift (§20.5).

# 4. Accounts

1. **Account types**, each with its own icon and hue:

   | Type | Group | Holds | Tax treatment |
   | --- | --- | --- | --- |
   | `checking`, `savings`, `money-market`, `cd` | Banking | cash | taxable (interest) |
   | `credit-card` | Liabilities | a negative balance | — |
   | `mortgage`, `heloc`, `auto-loan`, `student-loan`, `personal-loan`, `loan` (any other) | Liabilities | a loan with terms (§4.9) | mortgage and student-loan interest may be deductible |
   | `brokerage` | Investing | cash, stocks, ETFs, funds, bonds, options | taxable |
   | `ira` (traditional, SEP, SIMPLE) | Retirement | as brokerage | tax-deferred |
   | `roth-ira` | Retirement | as brokerage | tax-free (qualified) |
   | `401k`, `403b`, `457b` (traditional and Roth parts) | Retirement | funds, cash | tax-deferred / tax-free |
   | `hsa` | Retirement | cash, funds | triple tax-advantaged |
   | `529` (college savings) | Education | funds, cash, for one beneficiary (§4.8) | tax-free for qualified education |
   | `daf` (donor-advised fund) | Giving | funds, cash | deducted when contributed; grants are not deductible again (§10.9) |
   | `crypto-exchange` | Crypto | coins, fiat cash | taxable |
   | `crypto-wallet` (self-custody) | Crypto | bitcoin | taxable |
   | `precious-metals`, `collectables`, `real-estate`, `vehicle`, `other-asset` | Physical assets | items, each with its own basis and value (§4.10) | gains on collectables and metals: the collectables rate |

   A `daf` counts in no one's net worth by default: its money is already given away.
   **Count in net worth** on the account overrides that.

2. **Every account has** a name, its type, the institution, an optional masked number (last
   4), its owner, an **active** switch (a closed account stays
   for history and taxes), notes, and how it is kept current (§4.3).
3. **How an account is kept current**, one or more of:
   1. **manual**: transactions and balance snapshots typed in;
   2. **file import**: **OFX and QFX** files (the structured downloads most US banks and
      brokers offer; brokers' files also carry positions and trades), read with ofxtools;
      CSV, with a saved column mapping per institution; and brokers' and exchanges'
      trade-history CSVs. Imports are idempotent: a re-imported file adds only what is new,
      matched by the file's transaction id (an OFX file's `FITID`) or by date, amount and
      payee;
   3. **statement import**: a **PDF statement**, read from its text layer, or a **photo or
      scan** of one, read with RapidOCR as receipts are (§12.8), all on the server. MoneyKata
      finds the statement's period, its transactions and its opening and closing balances,
      and shows them for the user to check and correct before anything is saved. The
      transactions must add up from the opening to the closing balance; where they don't,
      the difference is shown and nothing is saved until it is resolved or accepted. What it
      learns about an institution's layout is kept per institution, so the next statement
      needs fewer corrections. Imports are idempotent here too. The statement file is kept as
      a receipt attached to the account (§12);
   4. **bitcoin watch** (self-custody wallets): balances and transactions read by address or
      xpub (§4.6).

   No bank-aggregation service is used: the user brings the files (§24).
4. **Retirement accounts** also carry: the **contribution year** of each contribution (a
   contribution made 2027-03-01 may be for 2026), employer match and vesting for a 401(k), and
   the account holder's **birth year** (from the profile) for limits and RMDs. Contribution
   limits per year are a table shipped with the app and updated with it, which an admin can
   correct in Settings (§11.6).
5. **Crypto exchanges** (Coinbase, Kraken and the like) are kept current from their CSV
   exports and statements, one import mapping per exchange. Reading an exchange through its
   API comes later (§23).
6. **Self-custody wallets** hold **bitcoin**. Other coins and chains come later (§23).
   1. **What the account holds**: addresses, or an **xpub/ypub/zpub** from which addresses
      are derived (with a gap limit of 20 unused addresses by default).
   2. **Where balances and history come from**, set by an admin in Settings › Bitcoin:
      1. a **public explorer** with the Esplora API (mempool.space by default, or
         Blockstream);
      2. **the household's own node**: its own mempool or Esplora instance, an **Electrum
         server** (Fulcrum, electrs), or **Bitcoin Core** over RPC with a watch-only
         descriptor wallet. An own node keeps the household's addresses private, and is
         recommended. Its address is named by the admin, so the egress guard (§16.5) lets
         MoneyKata reach it on the LAN; its credentials are a secret (§17.4).
   3. The form **refuses anything that looks like a private key or seed phrase** (WIF, 64
      hex digits, 12 or 24 BIP-39 words), says why, and never stores or logs it.
7. **Transfers** between two of a user's accounts are matched (same amount, a few days apart),
   so they count neither as spending nor as income, nor as a buy or sell of cash.
8. **529 plans.** A `529` account holds funds and cash like a brokerage account, plus:
   1. **The plan**: its state and name, the **beneficiary** (a person, §10.7, or a user), the
      opening date, and the state tax deduction the owner expects per year (typed: state
      rules are not modelled, §11.18).
   2. **Contributions** record who contributed (the owner, or a named relative), so gifts to
      the beneficiary can be totalled per contributor per year against the **annual gift
      exclusion** (in the tax tables, §19.11). A **five-year election** (superfunding)
      spreads one contribution over five years of exclusions and is shown that way.
   3. **Withdrawals** are matched with **qualified expenses** (tuition and fees, room and
      board, books, a computer, K-12 tuition, apprenticeships, student-loan repayment), each
      with its receipts (§12). Each year shows distributions (from Form 1099-Q) against the
      qualified expenses, and the part not covered, whose earnings may be taxable (§11.10).
   4. **Rollover to a Roth IRA**: once the account has been open 15 years, it shows how much
      could still roll over to the beneficiary's Roth IRA under the lifetime limit (in the
      tax tables), excluding contributions of the last five years.
   5. **The Goal tab** shows the beneficiary's education projection (§9.2.2).
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
   3. **Payments**: a payment transaction from a bank account (matched as a transfer, §4.7) is
      **split** into principal, interest, escrow, PMI and fees by the schedule. The user can
      correct a split from the servicer's statement. Principal beyond the schedule is
      recorded as an **overpayment**.
   4. **Reconciling**: the servicer's statement balance can be typed in on a date, and a
      difference from the computed balance is shown until it is explained (a fee, a missed
      payment, a wrong rate).
   5. **The loan's screen** shows the balance, the rate, the payoff date, interest paid to
      date and still to pay, principal paid this year, the schedule, and the **payoff
      planner** (§9.10). A mortgage linked to a `real-estate` item shows the **equity** and the
      **loan-to-value**, and when PMI can be dropped (on request at 80% of the original
      value; automatically at 78%).
   6. **Taxes**: mortgage interest, points and PMI (Form 1098), and student-loan interest
      (Form 1098-E) appear in Taxes (§11.12).
10. **Physical assets.** A physical-asset account (`precious-metals`, `collectables`,
    `real-estate`, `vehicle`, `other-asset`) holds **items**:
    1. **Every item has** a name, a category, a description, the **date acquired**, how it
       was acquired (bought, a gift, inherited), the **cost basis** (price plus premium,
       fees, shipping and improvements; a gift's carried-over basis; an inherited item's
       value at death), the quantity, where it is kept, a serial or certificate number, its
       condition or grade, the insured value and policy, **notes** (Markdown), and photos
       and documents (purchase receipt, appraisal, certificate, title), stored as receipts
       (§12).
    2. **Valuation**, one of:
       1. **spot**, for precious metals: the item's **fine weight** (weight per unit, in troy
          ounces, grams or kilograms, times purity, such as .9999, .925 or 22k, times
          quantity) times the metal's spot price (§7.3), adjusted by the premium or discount
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
       is the **primary residence**, and the loans secured by it (§4.9.5).
    5. **Selling** an item records the date, proceeds and fees, and realizes a gain or loss,
       flagged on Form 8949 as a **collectable** where it is one (metals included), which the
       tax tables tax at the collectables rate. A loss on personal-use property (a car, a
       home) is shown as not deductible (§11.13).
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
       OFX file's ledger balance, a statement's closing balance (§4.3.3), or a balance the
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
       marked in Accounts, and raises an alert after 7 days (§15.11).
    5. **Duplicate suspects** are flagged, never merged silently: two identical rows on one
       day ask *both real?* the first time, and the answer is kept.
    6. **Ticking off** (optional, for accounts kept by hand): pick a statement's closing date
       and balance, tick transactions as cleared until the difference is zero, and the period
       is marked **reconciled**. Editing a transaction inside a reconciled period asks first.

# 5. Holdings, lots and transactions

1. **Instruments** are kept once per server: symbol, name, class (`cash`, `equity`, `etf`,
   `mutual-fund`, `bond`, `option`, `crypto`, `metal`, `other`), and for options the
   underlying, right (call/put), strike, expiry and multiplier (100 by default). An option's
   symbol follows OCC (`AAPL  261218C00250000`) and is shown as `AAPL 18 Dec 26 250 C`.
2. **Lots** are created by buys and by transfers in with a cost basis. A transfer in without a
   cost basis asks for one, and the lot is marked *basis missing* until it has one. Taxes
   lists these (§11.4).
3. **Sales consume lots** by the account's **lot method**: FIFO (the default), LIFO, HIFO,
   specific identification (chosen per sale), or **average cost** (mutual funds, and crypto
   where elected). The method in force at the sale is recorded on it.
4. **Corporate actions**: splits, reverse splits, symbol changes, spin-offs (manual basis
   allocation), mergers (cash and/or stock) and return of capital adjust lots, never history.
5. **Dividends and interest**: qualified and ordinary dividends, reinvestment (a dividend plus
   a buy), and capital-gain distributions, with the classification the 1099 will use.
6. **Bank transactions** have a payee (normalised by **payee rules**), a category (§10.2), an
   optional split across categories, a memo, tags, and receipts.
7. **Categorisation rules**: an ordered list per user, first match wins. A rule matches the
   payee (text or `re:`), amount range, account and direction, and sets the category, tags and payee. Rules apply on import, and on demand to
   the uncategorised transactions.
8. **Editing history** is allowed. Every derived figure (balances, lots, gains, budgets,
   charts) follows on the next request. An edit that changes a closed tax year's realized
   gains asks for confirmation first.

# 6. Positions and options

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
   one (§7.5), otherwise the user's manual mark, otherwise intrinsic value, labelled as such.
8. **Wash sales**: a loss sale with a purchase of the same or a *substantially identical*
   instrument within 30 days either side is flagged, its disallowed loss computed and added to
   the replacement lot's basis. This covers the user's own accounts, IRAs included, and the
   accounts of anyone the user marks as their spouse. Options on the same underlying are
   flagged for review, not decided (§11.3).
9. **Gain/loss views**: realized by year, month, account, instrument and short- or long-term;
   unrealized now; and **per trade** for options (open date, close date, premium in and out,
   P/L, return on capital at risk).

# 7. Prices

1. **What prices must be**: **free** for a household to use, and **daily**. An end-of-day
   close is enough, and a delay of hours is fine: MoneyKata is not a trading app and fetches
   no intraday quotes. A source that needs a paid plan can be added (§7.2), but none is
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
      (*set*, with when and by whom; a key is a secret, §17.4), its order of preference per
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
   | Silver, platinum and palladium spot | **SLV**, **PPLT** and **PALL** from Tiingo, divided by each fund's metal per share | free | the metal per share ships with the tax tables (§19.11) and is updated with them; within a fraction of a percent of spot |
   | Options | **Massive** (formerly Polygon.io), Basic plan | free | end-of-day prices and two years of history; 5 calls a minute, each page of a result counting as one |
   | Treasuries, I bonds and EE bonds | computed | — | from the Treasury's published yield curve and savings-bond rates, which are free official data |
   | No free ticker: 529 portfolios, 401(k) collective trusts, individual corporate and municipal bonds | **manual** | — | a value from a statement or an import, or a typed price, with its date. A statement value older than 90 days is marked stale and raises an alert (§15.11) |

4. **Schedule**: once a day, after the US market close (6:00 PM Eastern by default), a
   background task loads the day's close for every **held or watched** instrument, and
   backfills history when an instrument is first held. **Refresh prices** does the same on
   demand. Requests are spread to stay inside each source's limits (Tiingo's 50 an hour
   means a few hours for a large household). A source that fails falls back to the next one
   for that class; Settings shows the last error, and a failure lasting past the alert
   threshold raises an alert (§15.11). Intraday quotes are not fetched.
5. **Option marks**: the day's close from the source that serves options, else manual or
   intrinsic value (§6.7). A close older than the last trading day is marked stale. Greeks
   are out of scope (§23).
6. **Stored prices** are kept: daily closes for ever.
   Charts read stored prices only, never a price source during a request.
7. **Every price carries its source and `as_of`.** The UI shows *delayed* or *as of 4:00 PM*
   on every value derived from it. A price older than a threshold (2 trading days for a
   stock) is marked stale.
8. **US dollars only**: every account, holding, price and total is in USD. Prices are fetched
   in USD, including crypto and metals spot. An instrument that trades only in another
   currency is priced by hand.
9. **Linked servers never call price sources for each other.** A peer's shared data carries its
   own values and their `as_of` (§14.5).

# 8. Portfolios and charts

1. **A portfolio** is a named set of accounts (or chosen holdings of them), owned by a user
   and shareable like an account (§13). A portfolio may include an account shared with its
   owner at `read`.
   1. **Viewers see only the accounts in it that are shared with them.** The others are
      hidden, and left out of every figure, chart and holding the viewer sees, so the
      portfolio's value is the value of what they can see. This holds across a link too.
   2. **Sharing a portfolio** whose accounts are not all shared with the people chosen: the
      Share dialog names the accounts each of them can't see and offers **Share these
      accounts too** (at read, and only for accounts the owner may share). Declining keeps
      them hidden from those people.
   3. A portfolio never includes an account from a linked server: linked data is shown only
      in its own window (§15.10).
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

# 9. Projections

1. **A projection** asks how money will grow and what it will pay for. It has an owner, a
   name, a **goal type** (§9.2), what it is **built on**, and whether it is **active**
   (§9.7). It is shared like an account (§13.3).
   1. **Built on** chosen accounts, a portfolio, or a typed amount for a what-if. Built on
      accounts or a portfolio, it starts from their **current values** each time it opens,
      with their *as of*, and from their allocation by asset class.
   2. **Contributions**: an amount, its frequency, growth per year, and until when. For
      retirement accounts they are capped by the limits of §4.4.
2. **Goal types.** All three use the same models (§9.4).
   1. **Retirement**, for one person or a **couple**: each person's birth year and
      retirement age, and the accounts that are theirs. After retirement come
      **withdrawals** (the 4% rule, a fixed amount rising with inflation, or a percentage
      of the balance) set against **other income**: Social Security from an age, a pension,
      each with its amount. The answer: the **chance the money lasts** to the horizon (age
      95 by default), and the balance by age.
   2. **Education**, for one beneficiary, built on their 529 accounts (§4.8). The
      beneficiary's birth year gives the first year of school. The user sets the years of
      school and the yearly cost in today's dollars: typed, or a shipped average of tuition,
      fees, room and board for public four-year (in-state) and private nonprofit four-year
      colleges, from the National Center for Education Statistics' *Digest of Education
      Statistics* (table 330.10, public domain, updated yearly and shipped with the tax
      tables), and the contributions,
      flagged where one person's gifts pass the annual exclusion (§4.8.2). The answer: the
      projected balance against the cost, the **percentage funded**, and the monthly
      contribution that would fund it fully. A 529's **Goal** tab shows this projection.
   3. **Savings target**: an amount by a date (a house deposit, a car), built on any
      accounts. The answer: the **chance of reaching it** by the date, and the monthly
      saving that would.
3. **Assumptions**, kept once per user in **Profile › Assumptions**: expected return and
   volatility for each asset class (US stocks, international stocks, bonds, cash, crypto,
   real estate, metals), general inflation (2.5% by default) and education inflation (5% by
   default). Every projection uses them unless it overrides a figure, so the user's
   projections and the payoff planner (§9.10) agree with each other. Fees per projection.
   1. **Bitcoin models.** For the bitcoin in what a projection is built on, the user can
      choose a published model in place of the crypto assumption, in Profile › Assumptions
      or per projection. Other coins keep the crypto assumption. Each model gives a median
      path from today's price and a range around it:

      | Model | What it is | Its range |
      |---|---|---|
      | **Your assumption** (the default) | log-normal at the crypto return and volatility above | the Monte Carlo fan |
      | **Power law** (Santostasi) | price = A × (days since the genesis block)^n, n ≈ 5.8 | the fit's spread, about a factor of two either way |
      | **Log regression** (the "rainbow chart") | a logarithmic curve fitted to the price history | its bands, from the fitted lows to the fitted tops |
      | **Stock-to-flow** (PlanB) | value from the ratio of supply to new issuance, stepping up at each halving | its published band |
      | **Saylor, Bitcoin24** (2024) | $3M, $13M and $49M by 2045 (bear, base, bull) | the bear and bull cases |
      | **ARK Invest** (2030 targets) | $500K, $1.2M and $2.4M by 2030 (bear, base, bull) | the bear and bull cases |

      1. **Compare models** shows every model's median path on one chart (log scale) with
         the price history behind it, and a table of each model's figures for 2030, 2035 and
         2045.
      2. **Each model states its source and record.** Stock-to-flow has run below its own
         band since 2022; the targets of Saylor and ARK are forecasts by people with a stake
         in the outcome; the curve fits describe the past and say nothing about why it
         should continue. MoneyKata shows these as models others publish, not as its own
         view, and not as advice (§1.16).
      3. **Their figures ship with the app**, dated and with their source, in Settings ›
         Tax tables, and are updated with it (a new ARK target, a refit of the power law).
      4. A projection that uses a model with bear, base and bull cases shows those three
         paths in place of a fan, since they are not percentiles.
4. **Models:**
   1. **deterministic**: future value at a constant rate, in nominal and today's dollars;
   2. **Monte Carlo**: *N* runs (1000 by default) drawing yearly returns from the asset
      classes' mean and volatility (normal or log-normal; historical bootstrap later), showing
      the 10th/50th/90th percentile **fan** and the type's answer (§9.2).
   3. **Glide path** *(later)*: the allocation shifting toward bonds as the goal nears, as
      age-based 529 portfolios and target-date funds do.
5. **Tax-aware buckets** (later): taxable, deferred and free balances projected apart, with
   RMDs from the required age and an assumed tax rate on withdrawals.
6. **Scenarios compare** side by side, for example retiring at 60 against 65, or contributing
   $500 more a month. Projections that are not active are the scenarios.
7. **Active projections** are the plans being followed.
   1. **At most one per subject**: one retirement projection per person or couple, one
      education projection per beneficiary, one per savings target. Making one active asks
      before turning off the one it replaces.
   2. **The baseline**: making a projection active stores its median path and its 10th–90th
      percentile band as of that day.
   3. **Tracking**: the actual balance of what it is built on, plotted against the baseline
      to date, and a status: **on track** inside the band, **ahead** above it, **behind**
      below it. Beside it, the type's answer run again from today's balance.
   4. **Changing an active projection's inputs** asks whether to **re-baseline**. Without
      it, tracking keeps comparing against the plan as it was made active.
   5. **Falling behind** raises an alert (§15.11), checked monthly, and resolves when the
      balance is back inside the band.
8. **Where active projections show:**
   1. the **Dashboard's Plans** card: one row each, with the type and name, the status, the
      type's headline figure (*87% chance of success*, *64% funded*, *$28,000 of $40,000 by
      2028*), and a small chart of the actual balance against the baseline;
   2. **on what it is built on**, when that is one account or one portfolio: a 529's Goal
      tab, an account's Overview, or a portfolio's *Projections* tab. A projection built on
      several accounts shows only on the Dashboard and the Projections screen;
   3. an active projection **shared with you** shows on your Dashboard only when you tick
      **Show on my Dashboard** on it, which is off by default, as **Count in my totals** is
      for accounts (§13.7). A linked household's projections show only in its window
      (§15.10).
9. **The computation runs on the server**, seeded so a scenario's figures are
   reproducible, and returns percentiles per year. It uses NumPy. The screen states its
   assumptions in full under the chart and says plainly that it is a model, not a forecast.
10. **Loan payoff planner** (on each loan's *Payoff* tab, §4.9.5). It compares the schedule
    with the user's **overpayment** plans:
    1. **Plans**, combined freely: an extra amount every month (from a date, until a date),
       an extra amount once a year (a bonus month), one-time **lump sums** on dates,
       **biweekly** payments (26 half-payments a year), and rounding each payment up.
    2. **Results** for each plan against the schedule: the new payoff date, months saved,
       **interest saved**, total paid, and the balance over time as two lines on one chart,
       with the amortization table of each.
    3. **Recast**: after a lump sum, a mortgage can be **recast** (the term kept, the payment
       lowered) instead of shortened. The planner shows both, with the servicer's recast fee.
    4. **Against investing the extra**: the same money invested at the user's expected
       return (§9.3) shows its value at the payoff date next to the interest saved.
       It is a comparison, not advice, and says so (§1.16).
    5. **Saved plans** are kept per loan. One can be marked **the plan I'm following**, and
       the loan's screen then shows whether actual overpayments are ahead of it or behind.
    6. Rates for an ARM's future resets are the user's assumption, shown as such.

# 10. Budgets, gifts and giving

1. **Budgets are per user, or per group** (a household budget a group shares at `write`).
   A budget covers chosen accounts and is monthly by default, or yearly per category.
2. **Categories** form a two-level tree (*Housing › Rent*). Each is an expense, income or
   transfer category. A default set ships, and each category may carry a **tax tag**
   (charitable, medical, business, childcare, education, …) that feeds Taxes (§11.5).
3. **Each period** has, per category, the **planned** amount, the **actual** from
   categorised transactions, and what remains, with optional **rollover** of the unspent or
   overspent remainder to the next period.
4. **Screens**: the month's categories as progress bars (green, then amber at 90%, red over),
   income against spending, cash flow (a Sankey from income to categories), trends of a
   category over 12 months, and the uncategorised transactions to sort.
5. **Recurring** transactions (rent, subscriptions, salary) are detected from history and
   listed with their next expected date and amount. A missed or changed one is flagged.
6. **Budget alerts** *(later)*: a category passing a threshold, a large transaction, a low
   balance, raised as alerts (§15.11).
7. **People and occasions.** Each user keeps their own list of **people** (on the Gifts
   screen):
   1. **A person has** a name, a relationship (child, parent, sibling, partner, friend, …),
      an optional link to a user of this server or of a linked server (§14), a **birthday** (the year optional, for
      their age), **anniversaries** (wedding, or any other, each with its own date), the
      **holidays** they get gifts for, a yearly **gift budget** or one per occasion, a
      reminder lead time (14 days by default), and notes (sizes, likes, what they already
      have).
   2. **Holidays** ship as a list with their dates computed per year: fixed dates
      (Christmas, Valentine's Day), rule-based ones (Mother's Day, Father's Day,
      Thanksgiving), and lunar or lunisolar ones (Hanukkah, Diwali, Lunar New Year, Eid
      al-Fitr) from shipped tables, plus **custom occasions** with a date of their own.
   3. **Upcoming occasions**: the next 60 days of everyone's dates, each with its budget,
      the gifts planned so far, and what is still missing. Those inside their lead time show
      on the Dashboard (*Emma's birthday in 9 days, no gift yet*), and an occasion entering
      its lead time raises an alert (§15.11).
8. **Gifts.**
   1. **A gift** is for one or more people and an occasion (and its year): a description,
      a **status** (*idea*, *planned*, *bought*, *given*), its cost, where it was bought, a
      link, notes, and receipts (§12). A cost is linked to its transaction, or typed. One
      purchase can be split across several gifts.
   2. **Ideas** are gifts without a date: a running list per person, to pick from when an
      occasion comes.
   3. **Gifts received** can be recorded too (from whom, for what), with a **thank-you
      sent** tick.
   4. **History**: per person, what was given in past years (so it isn't given twice) and
      the spending per year against their budget. Per year: gift spending by person and by
      occasion. Gift transactions are categorised *Gifts* in budgets (§10.2).
   5. **Privacy**: the people list and gifts are their owner's alone. A user may share a
      person (with their gifts) with another user or group, read or write, so a couple plans
      their children's gifts together. A gift for a person who is linked to a user is
      **never shown to that user**, even through a share, so a surprise stays one. For a
      user of a linked server, the owner's server leaves those gifts out before sending, so
      they never reach the other server.
   6. **Gift-tax flag**: money given to one person in a year (cash gifts, and 529
      contributions, §4.8.2) above the annual exclusion is flagged for Form 709 (§11.11).
9. **Charitable giving.**
   1. **A giving plan** per year, per user or per group (as budgets are): a **target** as a
      **percentage of income** (10% by default when one is set), or a fixed amount.
   2. **Income**, for the percentage, is one of: the year's transactions in *Income*
      categories (take-home pay, the default), a typed **gross income** (from a W-2 or a pay
      stub), or a typed estimate of AGI. The plan says which it uses.
   3. **Donations** come from transactions categorised under *Giving* (tax tag
      *charitable*, §10.2), or are recorded directly: the organisation, date, amount, and
      **type**: cash (card, cheque, transfer), **goods** (with their fair market value),
      **appreciated securities** (shares from a lot, §5.2: no gain is realized, and the
      deduction is the market value when held over a year, otherwise the basis), a
      **qualified charitable distribution** from an IRA (from age 70½, up to the year's limit
      in the tax tables), a **contribution to a donor-advised fund**, or a **grant** from
      one.
   4. **What counts toward the target**: everything that left the user's hands, with a DAF
      counted when it is funded (the default) or when it grants, as the plan chooses. A DAF
      contribution is never counted twice.
   5. **Organisations**: the name, EIN (optional), whether gifts to it are **deductible**
      (a 501(c)(3) charity, or not, such as a political campaign or a person), causes (tags),
      and **pledges** (an amount a month or a year, shown as expected donations).
   6. **The Giving screen**: given against the target and against the pace to date, the
      projected year end, giving by organisation, cause and type, the DAF's balance and its
      grants, the percentage of income over past years, and the donations missing an
      acknowledgement that the tax rules require (§11.9).

# 11. Taxes

The Taxes screen gathers, for one **tax book** (one user or married couple, one tax year,
§11.14), what a preparer or tax software needs. It
produces worksheets and exports. It never files, and says so (§1.16).

1. **Realized gains and losses**: every sale and closed option in taxable accounts, as **Form
   8949** rows (description, acquired, sold, proceeds, cost basis, adjustment code and
   amount, gain or loss), split into short- and long-term and by the box (A/B/C, D/E/F) that
   the broker's basis reporting determines, with **Schedule D** totals.
2. **Exports**: Form 8949 CSV, **TXF** (which TurboTax and others import), and a PDF summary
   for a preparer. Each export says what it covers and what it does not.
3. **Wash sales** found (§6.8), with the disallowed amounts and the replacement lots, and
   the flags left for review.
4. **Missing or doubtful data**: lots without a basis, sales without a matching lot, options
   with an unresolved expiry, transfers between users' accounts (a gift's carry-over basis),
   and crypto without a known acquisition.
5. **Income**: interest (1099-INT), dividends ordinary, qualified and capital-gain
   distributions (1099-DIV), foreign tax paid, and crypto income (staking, rewards) at fair
   value when received.
6. **Retirement**: contributions per account against the year's limits (with catch-up by
   age), Roth eligibility by MAGI as the user enters it, backdoor-Roth steps (non-deductible
   contribution, conversion, Form 8606 figures), distributions, and RMDs due.
7. **Deductions and credits**: totals of tax-tagged categories (§10.2) with their
   transactions and **receipts**. Charitable gifts above the substantiation threshold show
   whether a receipt is attached. Medical, childcare, education, HSA, and estimated tax
   payments by quarter.
8. **Documents checklist**: the 1099s, W-2s and statements expected for the year from the
   accounts held, each marked received (attach the PDF, §12) or missing (§11.16). A received 1099-B can
   be **reconciled** against MoneyKata's own totals, with the differences listed.
9. **Charitable giving** (§10.9): deductible donations by organisation and type (cash,
   goods, appreciated securities, DAF contributions; QCDs apart, since they are not
   deducted), each with its acknowledgement: a written acknowledgement is flagged as
   missing for any single gift of $250 or more, goods over $500 in a year note Form 8283,
   and an item over $5,000 notes that it needs an appraisal. Grants from a DAF and gifts to
   non-deductible organisations are listed apart, as not deductible.
10. **Education (529)** (§4.8): contributions per beneficiary and per contributor (with what
    the owner noted about the state deduction), distributions from Form 1099-Q against the
    qualified expenses and their receipts, and the part not covered, whose earnings may be
    taxable with a 10% additional tax. MoneyKata shows the figures. The preparer applies the
    rules, and the coordination with education credits.
11. **Gifts** (§10.8.6): each person who received more than the annual exclusion in the
    year, from cash gifts and 529 contributions, with the five-year 529 elections still
    running, as a prompt to file **Form 709**.
12. **Loans** (§4.9.6): mortgage interest, points, PMI and property tax paid through escrow
    (Form 1098) per property, and student-loan interest (Form 1098-E).
13. **Physical assets** (§4.10.5): sales of items, with collectables (metals included) marked
    on Form 8949 for the collectables rate, and losses on personal-use property shown as not
    deductible. A sold primary residence shows its gain and the years owned and lived in;
    the exclusion is the preparer's to apply.
14. **Tax books.** A tax book is the tax record of one **tax year** for one user, or for a
    married couple filing jointly. Each household member who files has their own, and a
    couple filing separately has two.
    1. **Filers**: one user, or two who are married. Creating a tax book names the year and
       the filers. A user named as a filer by someone else accepts before the tax book counts
       their accounts.
    2. **Accounts counted**: the filers' own accounts, each counted once even when the filers
       share it with each other. The owner can add an account they can see (a custodial
       account in a child's name) or leave one out, and the panels say what was left out.
    3. **Helping**: the filers hold the tax book as its owners. Anyone else sees it only
       through a share to users and groups, never to a linked server (§13.3). A user who helps
       prepare the return, such as a grown child or a preparer with an account here, gets
       **write**: they can edit filings, attach documents and resolve issues, but not delete
       the tax book or change its sharing.
    4. **New tax book** copies the filers and accounts from the year before, and turns last
       year's received documents into this year's expected ones (§11.16).
15. **Filings**: one per return: federal (Form 1040), a state's or a locality's. An
    **amended return** is a filing of its own that names the one it amends. Each filing has:
    1. the jurisdiction, the form, and the **filing status** as typed (MoneyKata never
       chooses it);
    2. who prepared it, and how it was sent (e-file or paper);
    3. its **progress** (not started, in progress, filed, accepted or rejected), the due date
       (federal from Settings › Tax tables, others typed), an **extension** (date filed, new
       due date), the date filed, and the confirmation or submission number;
    4. the **result**: the refund or the amount owed, matched to the transaction that paid or
       received it, and any overpayment applied to the next year;
    5. the **estimated payments** for its jurisdiction, by quarter, matched to transactions
       (§11.7);
    6. its **documents** (§11.16.2): the forms as filed, and what the tax authority sent.

    A filing past its due date that is not filed and has no extension shows in the
    Dashboard's *Needs attention*.
16. **Tax documents**: each has its form, who issued it, the account it is for, notes, and
    its file, which is kept as a receipt (§12) with the same storage and protection.
    1. **Received**, kept in the tax book: W-2s, 1099s, 1098s, 1095s, K-1s, 5498s and
       property-tax bills. They make up the checklist of §11.8, expected from the accounts
       held and last year's documents, each received or missing.
    2. **Filed**, kept in a filing: the return as filed with its schedules, the e-file
       acknowledgement, an extension, the preparer's copy and worksheets, and what the tax
       authority sends, such as notices, letters, the reply and transcripts. MoneyKata
       doesn't produce these. It keeps them because next year's preparation often needs
       them.
17. **Carried forward**: on each filing, the figures next year needs, typed from the filed
    return: adjusted gross income (needed to sign next year's e-filed return), total tax, the
    refund or amount owed, the overpayment applied, capital-loss carryovers (short and long
    term), the Form 8606 basis, and charitable-contribution carryovers. The next tax book
    shows them under **From last year**. It also puts the capital-loss carryover in its
    Summary and the 8606 basis in the backdoor-Roth figures (§11.6), and shows last year's
    total tax beside the estimated payments.
18. **What MoneyKata does not do**: compute the tax owed, choose a filing status, apply state
    rules, or decide questions of judgement (substantially identical, cost-basis elections).
    It shows the numbers and their sources.

# 12. Receipts

1. **Upload** from the browser: drag and drop, or the file picker. One or many at once.
   Taking a photo of a receipt with a phone belongs to the mobile PWA (§23).
   Formats: PDF, JPEG, PNG, WebP, and HEIC, the format of iPhone photos (converted to JPEG
   for display, with the photo's orientation applied). Each file is at most
   25 MB (a Setting).
2. **Stored on disk**, not in the database, under the data directory as
   `receipts/<random-id>.mkr`, **encrypted** (§18.3) and written once, never changed. The
   database holds the metadata: owner, original name, type, size, hash, upload time, date,
   amount, payee, notes, tags and links. Identical files are stored once, found by the hash
   in the database, never by the file's name.
3. **Links**: a receipt can be attached to any number of transactions, tax items (a donation,
   a medical expense) or tax documents (a 1099), physical-asset items (a purchase receipt,
   an appraisal, a certificate, photos, §4.10), loans (a closing disclosure, a statement),
   529 qualified expenses, gifts and donations, or to nothing yet (the **inbox**). Attaching
   one suggests matching transactions by amount and date.
4. **Viewing**: thumbnails in a grid, a viewer with zoom for images and the browser's own PDF
   viewer for PDFs, served `Content-Disposition: inline` with `Content-Security-Policy:
   sandbox` and `X-Content-Type-Options: nosniff`, from a path that needs the session. The
   server checks the type by the file's content, never by its name, and refuses anything else.
5. **Thumbnails** are made on upload (Pillow for images, pypdfium2 for a PDF's first page)
   and stored beside the file.
6. **Sharing** follows what the receipt is attached to: whoever can read a transaction can
   see its receipts. An unattached receipt is its owner's alone. Receipts cross a link only
   when the owner ticks **Include receipts** on that share, and then only as encrypted files
   in the other side's linked copy (§14.5, §14.9).
7. **Retention**: a receipt is deleted only by its owner and only when nothing links to it.
   The file stays while any receipt row names its hash, deleted or not (`schema.md` §4).
   Backups include the receipts directory (§17.6).
8. **Reading receipts (OCR)**: MoneyKata reads the date, total and merchant from each receipt
   **on the server, with RapidOCR**, and suggests the transaction it belongs to. Nothing
   leaves the server, and no external service, model download or GPU is involved.
   1. **What it produces**: the receipt's full text, and **suggested fields**: date, total,
      merchant, and where printed, tax and the card's last four digits. Each field carries a
      confidence. These are **suggestions**: they fill the receipt's empty fields, marked
      *read from the receipt*, and the user confirms or corrects them. OCR never overwrites a
      value a person entered, and never attaches a receipt by itself.
   2. **The pipeline**, per receipt:
      1. **PDF with a text layer** (an emailed invoice, a downloaded statement): the text is
         read with pypdfium2, with no OCR. A page counts as having a text layer when it gives
         at least 20 characters.
      2. **Images and scanned PDFs** are prepared first. Pillow applies the EXIF orientation,
         converts HEIC, converts to greyscale, and scales the long side to 2,000 pixels.
         pypdfium2 renders at most the first 3 PDF pages at 300 DPI.
      3. **RapidOCR** (the `rapidocr` package on **ONNX Runtime**, CPU only) runs the
         PP-OCR models: text detection, orientation classification, then text recognition.
         It returns each line's box, text and confidence. Skewed, curled and faded thermal
         receipts are within what these models are trained for.
      4. **Lines are put in reading order** from their boxes, and amounts that the
         recognizer split are joined (`14 2.18` → `142.18`).
      5. **The field parser** (MoneyKata's own code, rules plus tests):
         1. **total**: the amount on a line labelled TOTAL, AMOUNT DUE, BALANCE DUE, GRAND
            TOTAL or similar, skipping SUBTOTAL, TAX, CHANGE, CASH, SAVINGS and TIP lines,
            preferring the last such line; failing that, the largest amount;
         2. **date**: every common format (`10/09/2026`, `2026-10-09`, `09 OCT 26`,
            `Oct 9, 2026`), the most plausible one: not in the future, not before the
            account's opening;
         3. **merchant**: from the top lines, normalised by the user's payee rules (§5.7) and
            matched against payees they already have;
         4. **card**: `XXXX1234`, `****1234`, `ending in 1234`.
      6. **Matching**: the user's transactions (in accounts they can write to) with the same
         amount, within 5 days of the date, ranked by date distance and payee similarity. A
         transaction up to 25% larger also matches, to allow for a tip added after the
         receipt was printed. The best match is offered as *Attach to …*, with the next two
         as alternatives.
   3. **Models ship with the app.** The PP-OCR ONNX model files (detection, orientation,
      English/Latin recognition, about 15 MB) are committed and pinned by SHA-256, like the
      browser libraries. They are loaded from the install directory, and RapidOCR is
      configured with their local paths so it never tries to download a model at run time;
      the egress guard (§16.5) would refuse it anyway. Other scripts' recognition models
      (Chinese, Japanese, Korean, Cyrillic, …) can be added later the same way.
   4. **It runs as a background job**, never in a request:
      1. an upload queues the receipt and answers at once; the receipt shows *Reading…* until
         the job finishes, and the live-updates stream (§15.6) refreshes it;
      2. jobs run **one at a time** (a Setting, 1 by default) in a **separate worker
         process** with ONNX Runtime limited to 2 threads, a lower CPU priority, a memory cap
         (1.5 GB) and a 60-second limit per receipt. The worker is restarted after a crash or
         a timeout, so a hostile or broken file cannot take down the server;
      3. Pillow's decompression-bomb limit and a cap of 40 million pixels refuse oversized
         images before decoding;
      4. a receipt that fails is marked *couldn't read it*, with the reason, and stays usable
         with fields typed by hand;
      5. expected speed, to be measured on the target hardware: about 1–3 s per receipt on a
         current x86 CPU, about 3–10 s on a Raspberry Pi 5. A batch of uploads works through
         the queue.
   5. **Stored**: the full text in the database, indexed with SQLite **FTS5**, so the Receipts
      screen searches it (`blue bottle`, `142.18`). Beside it: the suggested fields with their
      confidences, the method (text layer or OCR), and the engine and model versions. Text and
      fields follow the receipt's sharing (§12.6), never cross a link, and are never written
      to Activity or the log.
   6. **Re-reading**: a receipt's **Read again** button, and in Settings › Receipts **Re-read
      all receipts** (after a model update), queue the jobs again. Only empty or
      OCR-suggested fields are replaced.
   7. **Settings › Receipts**: **Read receipts** on or off (on by default; off for a host too
      small to run it), the number of jobs at a time, and the queue's state (waiting,
      failed, last run).
   8. **Not in this version**: line items, handwriting, multi-receipt photos, currencies
      other than USD, and non-Latin scripts. A receipt that the parser can't
      make sense of still has its searchable text.

# 13. Users, groups and sharing

1. **Users, groups and sign-in**:
   1. A user has a unique username, a display name, a unique **email address**, an optional
      avatar, and a password stored as an argon2id hash. They sign in with username or email.
      The only password rule is a minimum length that admins set (12 by default).
   2. **The default admin.** A server with no users creates `admin` with a published default
      password at start. Its first sign-in leads only to a setup step: choose a password and
      give an email address.
   3. **Invitations.** Admins never set passwords. Creating a user (name, username, email,
      groups) emails an invitation link, and the user chooses their password from it.
   4. **Sign-up**, when an admin turns it on (it needs SMTP, and can be limited to email
      domains): a person gives their name and email, confirms the email, and waits on a
      *waiting for approval* screen until an admin approves or rejects the request.
   5. **Password reset** by an emailed link from *Forgot password?*. A changed email address
      takes effect only when a link sent to the new address is opened.
   6. **Two-step sign-in**, optional for everyone: a TOTP code from an authenticator app after
      the password, set up with a QR code; ten recovery codes shown once; and an admin's
      reset as the last resort.
   7. **Active.** Each user has an **active** flag, which admins switch off and on. An
      inactive user cannot sign in, and cannot be added to a share, here or from a linked
      server; shares they already hold give them nothing while they are inactive. Switching
      it off ends their sessions at once and shows an *account is disabled* screen, from which
      they can ask to be reactivated (once a week). Users and groups are deactivated rather
      than deleted.
   8. **Groups**: admins make named groups of users. Being an admin is membership of the
      built-in **Admins** group. The last active admin cannot be removed or deactivated.
   9. **Emails** (plain text): invitation, sign-up confirmation and decision, reset,
      email-change confirmation, password changed, two-step turned on or off, reactivated,
      and alerts (§15.11).
      In dev mode they are written to a folder (§20.7).
2. **Admins are not superusers of money.** An admin manages users, groups and Settings, and
   sees only the accounts and portfolios shared with them. Users are not deleted: a user
   who leaves is made inactive (§13.1.7), and their data stays.
3. **What can be shared**: seven kinds of item, each with one owner and its own list of shares:
   | Kind | A share includes |
   |---|---|
   | **Account** | its transactions, holdings, positions and receipts; a loan's payoff plans and a physical-asset account's items |
   | **Portfolio** | its charts and the accounts in it, as §8.1 says |
   | **Budget** | its categories, plan, actuals and trends (§10.1) |
   | **Person** | their occasions and gifts (§10.8.5) |
   | **Giving plan** | its target, pace, donations and organisations (§10.9.1) |
   | **Tax book** | its panels, filings and documents (§11.14.3) |
   | **Projection** | its inputs, results and tracking (§9) |

   Each can be shared with a **user** or a **group**, at:
   1. **read**: see everything about it. A read share cannot change it, attach receipts or
      re-share it.
   2. **write**: also change what the item holds: for an account, add and edit transactions,
      import, categorise and attach receipts; for the other kinds, edit their entries. A
      write share cannot delete the item, change its sharing, or see or change its secrets
      (keys and credentials), which stay the owner's.
   3. **People on linked servers**: any of the seven kinds can also be shared with named
      users of a linked server (§14), always **read**. Each server sends its peers its list
      of active users (display name, username and email), so they can be chosen like local
      users. Groups are not sent. When a remote user is deactivated, their shares are
      suspended. When the link ends, the shares are removed.
      1. **A remote user is a `User` record** with its `linkId` set, so it appears wherever
         a share is chosen, beside local users, under its server's name. It has no password,
         two-step or sessions (a `CHECK` enforces it), and its fields come only from its
         server (§14.3).
      2. **Only local users** appear where a user signs in, owns or changes something here:
         sign-in, Users and Groups, group membership (a group can hold write shares, and a
         remote user only ever reads), the Admins group, tax-book filers (§11.14.1), the
         spouse for wash sales, the owner of anything, and who receives alerts (§15.11). A
         person on the Gifts screen can be linked to a user of either kind (§10.7.1).
      3. **Settings › Linked servers** lists each link's users, read only.
4. **The Share dialog** lists every active user, then every active group, then the people on
   each linked server, each list alphabetical under a heading with a line on what sharing
   gives. Local users and groups have a three-way switch **None · Read · Write**. People on
   a linked server have **None · Read**, under the server's name, which notes that it
   confirms who they are. Each linked server with anyone set to Read has **Include
   receipts** (off by default, §14.5). A user who has access only through a group is shown
   *via* it. Nothing changes until **Save** (with **Cancel** beside it). When a share is
   removed, the receiver's access ends on their next request. Their own annotations, such as
   their tags on the account's transactions, are deleted.
5. **Through a group**: every member holds the share while they are in the group and it is
   active. A user with both a direct and a group share gets the higher level.
6. **A shared account appears in the receiver's lists** with a *shared with me* mark, the
   owner's avatar, and the level (an eye for read, a pencil for write). The owner's lists
   mark *shared by me* and how many people have it. Filters: All, Mine, Shared with me,
   Shared by me, From linked servers.
7. **A receiver's totals** (net worth, Dashboard) include shared accounts only if the
   receiver ticks **Count in my totals** on them, which is off by default. A spouse's accounts
   then count once, and a parent's shared accounts don't inflate a child's net worth. What a
   linked server shares never counts in this household's totals: it is shown only in its
   own window (§15.10).
8. **Activity** lists the changes worth showing, each naming who made it and what it is about,
   to the people concerned (the owner, the receivers, and admins for users and groups): shares given or taken away, accounts created, closed
   or deleted, imports, rule changes, links made or ended, and who did each. Amounts are
   never named (§3.8).
9. **Agents (MCP).** An AI assistant can read, and never change, what a user can see,
   through a **Model Context Protocol** endpoint at `/mcp` (Streamable HTTP).
   1. **Access tokens**: each user makes their own in **Profile › Access tokens**: a name,
      what it can read (everything the user can see, or chosen items), and an expiry (30
      days, 90 days by default, or a year). The token is shown once and stored as a hash.
      The list shows each token's name, scope, expiry and last use, with **Revoke**.
   2. **Read only, always.** There is no write scope. The tools list and read accounts,
      balances, holdings, transactions, portfolios, budgets, gifts, giving and tax panels,
      through the user's shares at the moment of the call. A write share gives a token no
      more than read.
   3. **Never through a token**: secrets, Settings, other users' data that isn't shared with
      the user, and linked households, whose access key is for a person at the screen
      (§14.9).
   4. A token works only at `/mcp`, never at `/ui/api`. It stops when it is revoked or
      expires, and when its user is made inactive. Each call is recorded in Activity under
      the token's name, and calls are limited to 60 a minute per token.

# 14. Linked servers

Two households, each with its own MoneyKata on its own LAN, share read-only views with each
other: a parent and an adult child, partners who keep separate servers, or a client and their
preparer.

1. **A link joins two servers**, made by admins on both sides:
   1. Admin A creates an **invitation** on server A: a one-time **link code** (valid 24 hours)
      that holds A's address and the fingerprint of A's link key.
   2. Admin B enters the code on server B, which connects to A, checks the fingerprint, and
      sends B's own address and key. A's admin sees the request with B's fingerprint and
      approves it.
   3. Each server then holds the other's **Ed25519 public key**. Every call between them is
      signed with the sender's key over the method, path, body hash, a timestamp and a
      nonce. The receiver refuses a bad signature, a timestamp more than 60 seconds off, and a
      nonce it has seen. No shared secret ever crosses. The protocol is specified in
      `docs/link-protocol.md`.
2. **Reachability**: links are HTTPS between the servers' **link addresses**, a separate
   listener or path (`/link`) that admins can expose apart from `/ui`. Two LANs need one of:
   1. one side reachable from the other (a forwarded port or a reverse proxy). That side
      **serves** and the other **pulls**;
   2. both on one overlay network, such as **Tailscale**, **WireGuard** or ZeroTier. This is
      the recommended setup and needs no open port;
   3. *(not now)* a relay. MoneyKata does not run one (§23).

   A link works when **either** side can reach the other: the side that can't be reached pulls.
3. **What a link carries**: only what a user on one server has shared with named people on
   the other (§13.3.3), always **read**, never write. The shares travel with the data, and
   the receiving server shows each item only to the people it names. The receiving admin
   does not choose who sees what. They see each share only as its kind, its owner's display
   name, who it names and the date it was shared: its name and figures stay inside the
   encrypted linked copy (§14.9). A linked share cannot be re-shared on the other side, not
   even with another link. Each server also sends the other its **list of active users**
   (display name, username, email and stable id) and its **household name and avatar**
   (§19.1), at every pull. The receiving server keeps each remote user as a record, updated
   by its id: a new user is added, a changed name, username, email or active flag is updated
   in place, and a user no longer on the list is soft-deleted, and restored if they return.
   When the link ends, its users are soft-deleted. Shares that name a remote user keep
   pointing at the same record throughout.
   1. **Each item travels as its screens show it, worked out at the source.** A budget's
      actuals, a giving plan's pace and a tax book's panels are computed from accounts that
      may not be shared themselves. The owner's server sends the figures and the entries
      that make them up (a donation's date, organisation and amount; a Form 8949 row), never
      the accounts behind them. An account shared as well arrives as its own item. The
      receiving server never recomputes; it shows what arrived, with its age.
4. **How data moves**: the receiving server **pulls a snapshot** of each linked share on a
   schedule (hourly by default, and on demand). The snapshot holds each shared item as
   §14.3.1 says (for an account: balances, holdings, positions, transactions and series),
   and receipts and documents when the share includes them.
   It is versioned, and only changes travel. Each change is **signed by the source's link
   key**, so the receiver can check it again when it applies it later. The receiver keeps
   its last copy in the link's encrypted **linked copy** (§14.9) and shows its age (*as of
   2 hours ago*). Pulls run whether or not anyone has unlocked the copy. When the source is
   unreachable, the copy stays, marked stale. When the share or the link is removed, the
   copy is deleted at the next pull, or at once by the receiving admin.
5. **What crosses a link, and what never does**:
   1. **Receipts** (and a tax book's document files) cross only when the owner ticks
      **Include receipts** on the share to that link (off by default). Receipts are large and personal, so sending them is a choice
      made per share. They then travel with their dates, amounts, payees and the text read
      from them (§12.8), so the receiving side never runs OCR on them. Without the tick, the
      other side sees only how many receipts a transaction has.
   2. **Never**: secrets, categorisation rules, groups, gifts for a person linked to a user
      of that server (§10.8.5), the accounts behind a shared item's figures unless they are
      shared too, and anything not shared with someone on that server. Of the source's
      users, only the active-user list (§14.3) crosses. Prices travel only as values already computed, with their
      `as_of` (§7.9).
6. **Ending a link**: either admin ends it on their own side. The other side learns at its
   next call and deletes its copies. Ending a link deletes nothing on the source.
7. **Settings › Linked servers** lists each link: the peer's name and address, its
   fingerprint, state (active, unreachable since…, ended), the last pull, and what flows each
   way, with *Pull now*, *Pause* and *End link*. For the linked copy it shows the changes
   waiting to be applied, when its access key was made and by whom, and whether it is
   unlocked (by whom, and when it will lock), with *Create the access key* (§14.9.2), *Lock
   now* and *Reset copy* (§14.9.8). The section also sets **Release linked keys after**
   (§14.9.4), one hour unused by default.
8. **Audit**: each pull is recorded on both sides (who, when, which shares, how much
   changed). The receiving side records who viewed linked data, as for any account, and
   every unlock (who), failed unlock, release (unused, Lock now or restart), access key made,
   and reset of a linked copy.
9. **Linked copies: kept apart and encrypted**. What a link brings in is
   someone else's money. A copy of it should not sit readable on this server's disk or in
   its backups, or be readable by malware on this server while nobody is using it. Its
   access key protects it at rest. Who sees what in it is decided by the owner's shares,
   not by the key.
   1. **The linked copy.** Each link's received shares live in one folder under the data
      directory, `links/<link-id>/`, never in the main database:

      ```
      links/<link-id>/
        shared.db                 SQLCipher: accounts, holdings, positions, transactions,
                                  series, budgets, people and gifts, giving plans, tax
                                  books, receipt records, the text read from receipts,
                                  thumbnails, and what has been applied
        receipts/<random-id>.mkr  one encrypted file per receipt (§14.9.6)
        inbox/<sequence>.mks      sealed changes waiting to be applied (§14.9.5)
      ```

      The main database holds only what is needed while the copy is locked: the link, the
      shared items' ids, kinds, owner's display name and the people they name (not their
      names or values), the household's name and avatar, the copy's public key, and the
      inbox's length and newest `as_of`. File names are random, so the folder shows
      no names, payees or dates.
   2. **The access key.** Each linked copy has a random 128-bit **copy key**, shown once as
      **12 words** from the BIP39 English word list (the last word carries a checksum). The
      words are the copy's **access key**.
      1. **Made by the receiving admin**, when the link's first share arrives: Settings ›
         Linked servers › **Create the access key**. The server makes the copy key, shows the
         words once, and asks the admin to confirm they have saved them, typically in the
         household's password manager, where the people the shares name can reach them.
         Pulls into the copy begin then.
      2. Separate keys are derived from the copy key with HKDF-SHA256, each under its own
         label: the **database key**, which SQLCipher uses as its raw key (`PRAGMA key =
         "x'…'"`), and the **copy's private key** (X25519), whose public half is stored in
         the main database.
      3. The copy key is **never stored**, in any form. The server holds it only in memory
         while the copy is unlocked. There is **no master-key slot**: the master key (§18)
         cannot open a linked copy.
   3. **Unlocking.** The copy is unlocked for the whole server, not per user.
      1. When someone the copy's shares name opens its window (§15.10) while it is locked,
         the server asks them for the 12 words. It checks the checksum and that the words
         derive the copy's stored public key, then holds the copy key in memory. Nothing
         about it reaches the browser.
      2. While it is unlocked, **the owner's shares alone decide who sees what** (§14.3):
         each user sees only the items that name them. Anyone named can open the window
         without the words until the copy locks again. Knowing the words without a share
         opens nothing.
      3. **Wrong words**: five in a row make that user wait 15 minutes, and the copy
         accepts at most 20 attempts an hour from all users together.
   4. **Locking.**
      1. The key is **released after it goes unused** for the time set in Settings › Linked
         servers (§14.7), one hour by default. *Used* means a read made for a person: a
         screen or export in the linked household's window. Background work, such as
         applying a pull, does not count.
      2. A sweeper task checks every minute and locks each copy past its time. Locking closes
         the copy's SQLCipher connections, which wipes SQLCipher's own copy of the key, and
         overwrites the server's copy of the key bytes. Python cannot promise that no other
         copy lingers in memory until it is reclaimed, so this is a release, overwritten
         where possible, not a guaranteed erasure.
      3. It also locks at **Lock now** (in the linked household's window, and in Settings ›
         Linked servers for admins), which anyone the copy shares with can press, and when
         the server restarts.
      4. While a copy is locked, its window asks for the words. Nothing from it appears
         anywhere else at any time (§15.10).
      5. The window's header says who unlocked it and when it will lock: *unlocked by Alice
         at 14:05 · locks after an hour unused*. Every unlock, failure and release is
         recorded (§14.8).
   5. **Staying in sync while locked.** Pulls (§14.4) never wait for an unlock.
      1. Each pulled change, still carrying the source's signature, is **sealed** to the
         copy's public key and written to `inbox/` as the next numbered file. Sealing needs
         only the public key. The plain change is held in memory only while it is being
         sealed.
      2. Receipts are written straight into `receipts/` in the same way. They never wait in
         the inbox.
      3. The inbox is **applied** in order, in one transaction, as soon as the copy is
         unlocked. Each change's signature is checked first, and a change that
         fails stops the apply and is reported. Applied files are deleted. While a copy stays
         unlocked, new pulls are applied as they arrive.
      4. If the inbox grows past 1,000 changes or 500 MB, the server discards it and asks the
         source for a **full snapshot**, sealed the same way.
      5. A locked copy still shows its sync state from the main database: *synced 5 minutes
         ago · 12 changes waiting · locked*.
   6. **Encrypted files** (receipts and inbox changes) use one streaming format, so a 25 MB
      receipt is never held whole in memory.
      1. **Header**: magic and version (`MKR1`), a one-time X25519 public key, a random 32-byte
         salt, a 7-byte nonce prefix, and the chunk size (64 KiB).
      2. **Key**: HKDF-SHA256 over the X25519 exchange between the one-time key and the copy's
         key, with the salt, under the label `moneykata link receipt` or `moneykata link
         change`. Every file therefore has its own key.
      3. **Chunks**: each 64 KiB chunk is sealed with AES-256-GCM. Its nonce is the prefix, a
         4-byte chunk counter and a last-chunk flag, so a chunk cannot be reordered, dropped or
         cut off unnoticed. The associated data names the link, the receipt or change, and the
         chunk's number, so a file renamed or copied onto another receipt fails to open.
      4. `shared.db` records each receipt's file name, length and plaintext SHA-256, which came
         signed from the source. The hash is checked when the file is shown, so an older copy
         swapped in is caught.
      5. **Showing a receipt** streams it through decryption into the response. **Plaintext
         never touches the disk**: there are no temporary files, and thumbnails are kept in
         `shared.db`.
      6. **Writing**: each file is written under a temporary name, synced to disk and renamed
         before its row is committed. A sweeper removes files that no row names, left behind
         after a crash.
      7. This is the AES-GCM-HKDF streaming construction (the one Tink uses), built on the
         `cryptography` library. It needs no further dependency.
   7. **Who can open what.** The owner's shares decide what each user sees (§14.3), and the
      words decide whether the copy can be opened at all. Removing a share hides the item
      from that user at once, with no re-keying. New words are needed only if they reach
      someone who could also read this server's disk (§14.9.10).
   8. **Lost words.** **Reset copy** (Settings › Linked servers, admins) deletes the folder,
      makes a new copy key with new words, and pulls everything again from the source.
      Nothing is lost: the linked copy is only a copy, and the source keeps the data. The
      master key has a recovery phrase because it is the only way into this server's own
      data (§18.6); a copy key does not need one.
   9. **Backups** leave linked copies out (§17.6). After a restore, the admin makes a new
      access key for each link, and each copy is pulled in full from its source.
   10. **What this protects against, and what it does not.** A stolen disk, a backup that
       leaves the house, and this server's admin or root reading files while the copy is
       locked reveal nothing of a linked copy beyond its size, its number of receipts and
       when changes arrived, unless they also have the words. It does **not** protect
       against root, or malware running as the server, while the copy is unlocked: the key is
       then in the server's memory, and no design changes that. Releasing the key after an
       hour unused keeps that window short. Nor does it protect against someone with the
       words reading the copy's files outside the app. The source's owner is trusting the
       people they name and the household that keeps the words.
   11. **The engine**: SQLCipher through the `sqlcipher3` wheel, which bundles SQLCipher,
       opened as a second SQLAlchemy engine for each unlocked copy. Each copy keeps its own
       Alembic history (§17.1), which is applied when it is unlocked.

# 15. Web UI

1. **Frame**: drawn once around every signed-in screen, from one list of navigation entries;
   no screen draws or changes it.
   1. A **sidebar** pinned to the viewport: the household's avatar and name with the version
      (and a red **DEV** pill in dev mode), the navigation with count badges, and at its
      foot the signed-in user's
      tile with the **theme** button (crescent moon for dark, lightbulb for light, palette
      for the system's; a click moves to the next). A round button on its edge collapses it
      to icons and opens it again; the browser remembers which.
   2. The **help pane** on the right (§15.7), and a **toast** area for confirmations.
   3. Shared components: one popup menu (closes on choosing, Escape, or a click or focus
      outside), dialogs that trap focus and return it, styled tooltips that also show on
      keyboard focus and reach screen readers, and a **pager** for long lists (Transactions,
      Activity): a page size of 100, 500 or 1000 kept per browser, and rows that arrive while
      reading counted on an orange **+N new** pill instead of shifting the page. Every
      password field (a password, an API key, the SMTP or node password) carries an **eye**
      button at its right end that shows what was typed and hides it again (the eye struck
      through while shown), labelled for screen readers.
   4. An orange **update** pill under the brand when the server was upgraded since the page
      loaded; a click reloads.
2. **Navigation** (in this order):
   1. **Dashboard**: net worth and its change (day, month, year), the net-worth chart,
      allocation, accounts by group with balances, this month's budget, upcoming recurring
      transactions, occasions inside their reminder time (§10.7.3), giving against its
      target, the **Plans** card of active projections (§9.8), and stale prices, stale
      valuations, or sources and imports that need attention;
   2. **Accounts**: every account the user owns or holds a share of, grouped (Banking,
      Investing, Retirement, Education, Crypto, Giving, Liabilities, Physical assets), each with its type icon,
      institution, balance, change, when it was last updated, and sharing marks. **New account** offers a
      type picker, then the account form. An **account page** has the tabs *Overview*
      (balance chart), *Holdings* (investing only), *Transactions*, *Positions* (investing
      only), *Receipts*, *Reconcile* (banking, card, brokerage and loan accounts, §4.11),
      *Sharing* and *Settings* (how it is kept current, lot method, import mappings).
      Some types add tabs: a loan *Schedule* and *Payoff* (§4.9, §9.10); a 529
      *Contributions*, *Withdrawals* and *Goal* (§4.8); a physical-asset account *Items*
      (§4.10);
   3. **Transactions**: every account's transactions together, filtered by account, category,
      date, amount, payee and tag, with bulk categorise, split, attach receipt, and **Import**;
   4. **Portfolios**: the user's portfolios and those shared with them; a portfolio page with
      the charts of §8.2, its holdings, and its *Projections*;
   5. **Positions**: open and closed positions across accounts, with stocks, options and
      crypto as filters, and P/L per §6.9. **Record trade** opens the trade dialog, which has
      an option leg builder;
   6. **Budgets**: the month view, cash flow, trends, recurring transactions and rules;
   7. **Projections**: active projections first, with their tracking, then the scenarios;
      each with its inputs and the fan chart (§9);
   8. **Gifts**: *Upcoming* occasions, *People*, *Gifts* (ideas to given, and received), and
      *Spending* by person, occasion and year (§10.7, §10.8);
   9. **Giving**: the year's target and progress, donations, organisations and the DAF
      (§10.9);
   10. **Taxes**: the tax-book picker (year and filers), **New tax book** and **Share**, then
       the panels of §11, with *Filings* and *Documents* (received and filed, §11.14–11.17);
   11. **Receipts**: the inbox and every receipt, with a grid or list view and upload;
   12. **Watchlist** *(small)*: instruments the user follows without holding them;
   13. **Activity**: the changes of §13.8, newest first, filtered by account and person;
   14. **Users and Groups**, **Settings** (admins);
   15. **Alerts**: what needs the user's attention, with a live count on its badge (§15.11);
   16. the user tile opens **Profile** (name, email, avatar, password, two-step, alert
       emails, time zone (§17.9), assumptions for projections (§9.3), access tokens, birth
       year, spouse for
       wash sales) and **Sign out**.
3. **Privacy mode**: a button in the header (an eye) blurs every amount on the page until
   clicked again, for using the app with someone looking over your shoulder. The browser
   remembers it.
4. **Numbers**: tabular figures, right-aligned, with the dollar sign. Gains are green and
   losses red, *and* signed with + or −, so colour is never the only cue. Large values are
   abbreviated in charts only ($1.2M), never in tables.
5. **Every value derived from a price** shows its age on hover, and the header shows the last
   price refresh with a dot that turns amber when prices are stale (§7.7).
6. **Live updates**: the frame keeps one Server-Sent Events stream open (`GET
   /ui/api/events`). It carries fingerprints and counts, never data: prices refreshed, an
   import finished, a statement read, a share received or removed, a linked pull done, a
   background task finished (a backup, a re-encryption), a new alert, the badges' counts (Alerts among them), and the server's version. A screen whose data changed reloads it through
   its usual routes. The stream never extends the session, ends after a few minutes (the
   browser reconnects), and takes the page to sign-in or *account is disabled* when the
   session ends.
7. **Help pane**, on every screen:
   1. **F1** toggles it. While it is closed, a dim quarter-circle with a question mark sits in
      the page's top right corner, and grows into a green circle on hover ("Show help (F1)").
      The pane sits at the right edge; the split drags (up to half the window) and moves with
      the arrow keys. The browser remembers whether it is open and how wide.
   2. **The guides** are Markdown files shipped with the app: `web/ui/guides/<screen>.md`, and
      `<screen>-<panel>.md` for a screen's tabs or sections. **Per-account-type** parts
      (`guides/account-<type>.md`) are placed into the account page's guides by marker lines
      (`{{account-type settings}}`), and each price source has its own part for Settings ›
      Prices.
   3. **It follows the page.** As focus moves to a field, the pane scrolls smoothly to that
      field's heading and highlights it for a moment. That heading stays marked as the
      **active topic** (extra bold, underlined, with a solid ▶ to its left) until focus moves
      to another field with a heading of its own. A field is matched to a `##` heading by
      its label turned into an id ("Lot method" → `lot-method`), or to an id the heading lists
      (`## Lot method {#lots}`). Guides keep the page's order, so moving down the page never
      moves the guide up.
   4. **What a guide holds**: a short paragraph on what the screen is for, a screenshot, and a
      heading for every field, switch and button (what it is for, what to enter, its default),
      with examples for anything typed in a language of its own (rules, patterns, mappings).
      The Markdown is a subset: headings, paragraphs, lists, tables, code, quotes (shown as
      notes), images, links, bold, italic; raw HTML is shown as text.
   5. **Screenshots** come from the clickable mockup (`web/dev.sh help-shots`, dark theme,
      1280 px, WebP) and are committed.
   6. **Checks**: a test fails when a screen has no guide, a guide's screenshot is missing,
      a field's label finds no heading, or the next field down the page sends the guide up. Finance terms (cost basis, wash
   sale, RMD, TWR and IRR) get a short plain-language explanation in the guide of the screen
   where they appear.
8. **Accessibility**: everything works by keyboard, every control is labelled, contrast
   meets WCAG AA, and `prefers-reduced-motion` turns transitions off. Dark theme first, with
   light and system. **Desktop browsers only**: phone layouts are not built or tested, since
   phones will get a separate PWA with a narrower, focused set of features. English only,
   no i18n layer. Charts have a **table view** toggle (a screen reader reads the numbers) and
   honour `prefers-reduced-motion`.
9. **The clickable mockup**: one HTML file that opens from disk and sends nothing anywhere,
   showing every screen and dialog on sample data. Its purple **MOCK** pill (where the DEV
   pill goes) jumps to any screen, switches users, opens dialogs and changes state (prices
   stale, privacy mode). There are two files while the app is being built:
   1. **`docs/mockups/MoneyKata-mock.html`**, hand-written: the design reference for every
      screen. A change to what users see updates it in the same change.
   2. **`docs/mockups/MoneyKata-app.html`**, generated: `web/ui/mockup/build.py` inlines the
      app and an in-page fake backend, for the screens built so far, and `web/check` fails
      while it is out of date.

   When the generated file covers every screen, it replaces the hand-written one and takes
   its name. `docs/mockups/check.py` opens every screen, tab, Settings section and dialog of
   the hand-written mockup in headless Chromium and fails on any page or console error.
10. **Linked households.** What another household shares is a world of its own, so it is
    never shown together with this household's data. It opens in a **window of its own**.
    1. **Where to find them**: a click on the household's avatar at the top of the sidebar
       opens a menu of the linked households, with no title. A **Linked households** card on
       Accounts lists them too. Each entry shows the household's avatar and name, how many
       items it shares with you, and when it last synced, and no names or amounts. A
       household that shares nothing with you is not listed. With none, the avatar opens no
       menu.
    2. **Opening one** follows a plain link to `/ui/linked/<link-id>/` with
       `target="mk-linked-<link-id>"`, so a pop-up blocker doesn't stop it, a second click
       goes to the window already open, and it can be bookmarked. Whether it opens as a
       window or a tab is the browser's choice. It uses the same sign-in, so signing out in
       either ends both.
    3. **The window** is the same frame, read only:
       1. the household's **avatar and name** in place of this household's, always as the
          source server sets them (§19.1);
       2. the sidebar tinted with **a colour each user chooses** for that household, from a
          fixed palette that reads well in dark and light themes. A new household gets the
          next unused colour. The name, avatar and a header strip always show as well, so
          colour is never the only sign;
       3. a **header strip**: *griffin-parents · read only · synced 41 min ago · unlocked by
          Alice at 14:05 · Lock now*;
       4. the screens for the kinds shared with you: Dashboard (only what is shared with
          you), Accounts, Portfolios, Positions, Transactions, Projections, Budgets, Gifts,
          Giving, Taxes and Receipts. The navigation lists only the kinds you have something from. There is
          no Settings, Profile, Watchlist, import, sharing or editing;
       5. the user tile shows you, the local user, *viewing griffin-parents*.
    4. **Locked**: the window shows only the household's name and avatar and the request for
       the access key (§14.9.3). If the copy locks while the window is open, the window
       returns to that request.
    5. **Never mixed**: nothing from a linked household appears in this household's lists,
       totals, charts, search, portfolios, budgets, taxes or Activity.
11. **Alerts** tell someone that something needs them. Activity records what happened; an
    alert asks for an action.
    1. **What raises one**:
       1. **for admins**: a source that has failed for longer than the threshold in Settings
          › Alerts (48 hours by default): the bitcoin explorer or node, a price source, or a
          linked server's pulls; a backup that failed;
          a link's first share waiting for its access key (§14.9.2); and the yearly check of
          the master key's recovery phrase (§18.6.5). An admin's alert about someone else's
          account names its owner and source, never the account's name or figures (§13.2);
       2. **for an account's owner**: their wallet's explorer or node failing for longer
          than the threshold, and an account whose latest statement or import is older than
          its expected interval (a month and a half for a monthly statement), and a
          reconciliation mismatch left open for 7 days (§4.11);
       3. **for each user**: an occasion entering its lead time (§10.7.3), an option
          expiring within a week, a pledge due (§10.9), an active projection falling
          behind (§9.7.5), and budget alerts when they come (§10.6).
    2. **One alert per cause.** A failing source raises one alert, not one per attempt. It
       stays **open** while the cause lasts and is **resolved** by itself when the cause
       clears (the source answers again). A user can **dismiss** an open alert for themselves.
       Resolved alerts stay listed for 90 days.
    3. **The Alerts screen** lists open alerts first, newest first, then resolved ones. Each
       shows what it is about, since when, a link to the place to fix it, and **Dismiss**.
       Opening the screen marks the user's alerts as seen.
    4. **The badge** on the Alerts entry counts the open alerts the user has not seen. A new
       alert reaches the badge through the live stream (§15.6) without a reload, with a toast.
    5. **Emails**: each user chooses in Profile how alerts reach them by email:
       1. **each alert**: one email when an alert opens (not when it repeats or resolves);
       2. **daily summary**: one email a day at the time set in Settings › Alerts (07:00 by
          default, in each user's time zone, §17.9) listing the alerts opened since the last one, and none on a day without
          any;
       3. **none**: on screen only.

       Admins start on *each alert*, other users on *daily summary*. Without SMTP set up, the
       choice is shown but nothing is sent. Alert emails name the kind and the thing it is
       about, never amounts.

# 16. Architecture

1. One HTTPS address. `/` redirects to `/ui`. `/ui/*` serves the app and `/ui/api/*` its API.
   `/link/*` is the linked-server API (§14). `/mcp` is the read-only endpoint for agents
   (§13.9). `/healthz` is the health check. `/demo` serves the clickable mockup (§15.9) to
   anyone, without signing in: it holds only sample data, runs in a sandbox with an opaque
   origin, and can reach neither the app's cookie nor its API.
2. **Authentication**: server-side sessions for `/ui/api` (a random token stored hashed, in an
   HttpOnly, Secure, SameSite=Strict cookie, with an `Origin` check on every change; idle and
   absolute lifetimes are Settings). Signed peer requests for
   `/link` (§14.1). Neither is accepted on the other's path.
3. **Port 37373**, on all of the container's interfaces; the host's port mapping and firewall
   decide what reaches it. **Two listener modes**, one switch in `moneykata.toml`:
   **`proxy`**, plain HTTP behind haproxy, Caddy or nginx, which ends TLS (forwarded headers
   are trusted only from the configured proxy addresses); or **`tls`**, its own HTTPS
   listener with HTTP/2 (forwarded headers ignored). **`proxy`** is the expected setup.
   **`tls`** is for testing on a local network: given no certificate, the server makes a
   self-signed one on first start and keeps it in the data directory. It names the server
   and `localhost`, and the names and addresses listed in `[tls] names`, which are how
   browsers on the network reach it; a change to the list makes it again.
4. **Background tasks** in the server process: price refresh (§7.4), bitcoin wallet reads
   (§4.6), link pulls (§14.4), option expiry (§6.6), recurring detection (§10.5), backups
   (§17.6), receipt and statement reading (§12.8, §4.3, in its own worker process), and
   pruning. Each records its last run and error, which Settings shows.
   They run in a thread pool with per-provider rate limits and never block a request.
5. **Outbound calls** go through one httpx client with an **egress guard**: only the hosts of
   enabled price sources, the bitcoin explorer or node, and links; never loopback, link-local or cloud metadata
   addresses unless an admin allows one by name; with timeouts and response-size ceilings.
6. **Stopping**: on SIGTERM the server ends every event stream, lets requests in flight finish
   for up to 5 seconds, and stops; a second signal stops at once. **A refused start**: when it
   cannot start for a reason only an operator can fix (a config file it can't use, a file
   mode, a database from a newer release, a certificate it can't load), it says why in one
   `refusing to start:` line and exits 78 (`EX_CONFIG`). The example `compose.yaml` restarts
   it only on failure, three times at most, so a refused start isn't retried in a loop.
7. **Security policies** *(proposed, for review)*. One place for the rules every request
   passes through; other sections refer here.
   1. **Sessions**: a 256-bit random token in a cookie named `mk_session`, `HttpOnly`,
      `Secure`, `SameSite=Strict`, `Path=/ui`, stored as its SHA-256. A new token at sign-in
      and at every change of privilege (two-step passed, made admin), so a token from before
      sign-in never works after it. Idle lifetime 8 hours and absolute 30 days by default
      (Settings › Sign-in and sessions). Signing out, a password change and deactivation end
      every session of that user at once.
   2. **Re-authentication**: changing the password, the email address or two-step, making an
      access token, creating a linked copy's access key, sharing with a linked server, and
      exporting data each need the password again if it was last given more than 10 minutes
      ago.
   3. **Passwords**: argon2id (64 MiB, 3 passes, parallelism 1), the minimum length of
      §19.5, and no other rules. Checked against a shipped list of the 100,000 most common
      passwords, which are refused.
   4. **Cross-site requests**: `SameSite=Strict` plus an `Origin` check on every request
      that changes something; a missing or foreign `Origin` is refused with 403. No CORS: the
      API answers only its own origin.
   5. **Rate limits**, per client address and per user, answered with 429 and a
      `Retry-After`:
      1. sign-in, two-step codes and password-reset requests: 10 failures in 15 minutes lock
         that username for 15 minutes and slow that address (§13.1);
      2. linked copies' access keys: §14.9.3.3;
      3. the API: 600 requests a minute per session; uploads: 60 files an hour per user;
      4. `/mcp`: 60 calls a minute per token (§13.9.4); `/link`: 60 calls a minute per
         link.
   6. **Request limits**: JSON bodies up to 1 MB, uploads up to the size in Settings
      (25 MB by default), at most 100 MB of uploads in flight per user, and request headers
      up to 16 KB. Each upload's type is checked from its content, never its name (§12.1).
   7. **Response headers** on every response: the CSP of §20.3.3,
      `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
      `Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Resource-Policy: same-origin`,
      `Permissions-Policy` denying camera, microphone, geolocation and payment, and
      `frame-ancestors 'none'`. In `tls` mode, `Strict-Transport-Security` for a year.
      Receipt and statement files are served with `Content-Disposition`, their checked type,
      and a `sandbox` CSP, so a PDF can't run script in the app's origin. `/demo` has a CSP of
      its own: `sandbox allow-scripts allow-popups`, inline script and style allowed (the
      mockup is one file), and `connect-src 'none'`.
   8. **Errors** never include a stack trace, a SQL statement, a path on the host or a
      secret. Each error carries an id that is also in the log, so an admin can find the
      detail.
   9. **Logging**: no amounts, names of accounts or payees, secrets, tokens or passwords;
      user ids, record ids, routes and outcomes only (§3.8). Sign-ins, failures, lockouts and
      every admin action are logged and recorded in Activity.
   10. **TLS** (in `tls` mode): TLS 1.2 and 1.3 only, with the server's default modern cipher
       suites; HTTP/2.
   11. **Supply chain**: Python dependencies pinned with hashes in `uv.lock`; browser
       libraries vendored with their hashes in `manifest.json` (§20.3.1); the image built
       from a pinned base and rebuilt for security updates.
8. **API conventions** *(proposed, for review)*, for `/ui/api` and, where they apply, `/mcp`.
   The OpenAPI document is generated from the routes (§3.9).
   1. **Resources and methods**: plural nouns (`/ui/api/accounts`, `/ui/api/accounts/{id}`).
      `GET` reads, `POST` creates, `PATCH` changes the fields it sends, `DELETE`
      soft-deletes (`schema.md` §4) and returns 204. An action that is not a change of
      fields is a `POST` to a verb under the resource (`/ui/api/links/{id}/pull`).
   2. **Names and values in JSON**: field names camelCase, as in the database (`schema.md`
      §1). Ids are the prefixed strings of `schema.md` §2. Money is a decimal **string** in
      dollars with two places (`"1234.50"`); quantities and prices are decimal strings to
      their own scale (§17.3); floats are refused. Dates are `YYYY-MM-DD`; timestamps are
      RFC 3339 in UTC (`2026-10-12T14:05:00Z`, §17.9). A field with no value is `null`, never
      left out.
   3. **Errors** are `application/problem+json` (RFC 9457): `type`, `title`, `status`,
      `detail`, the error id of §16.7.8, and `errors`, a list of `{field, code, message}` so
      the UI shows each refusal at its field (§3.7). Codes are stable strings
      (`key-too-short`, `share-not-allowed`), listed in the OpenAPI document.
   4. **Status codes**: 200, 201 with `Location`, 202 for work that continues (§16.8.7),
      204, 400 for a malformed request, 401 when not signed in, 403 when not allowed, 404 for
      what doesn't exist *or* isn't visible to the caller (never revealing which), 409 for a
      conflict, 412 for a stale version, 413, 415, 422 for a valid request that breaks a rule,
      429, and 503 while the server is starting or a linked copy is locked.
   5. **Paging**: by cursor. `?limit=` (100 by default; 500 and 1000 allowed, §15.1.3) and
      `?after=<cursor>`; the response has `items` and `next` (a cursor, or `null`). Sorting
      with `?sort=field` or `-field` on the fields each list declares; filters as named query
      parameters.
   6. **Concurrency**: each record has a `version` that changes with every save. `PATCH` and
      `DELETE` send it in `If-Match`; a stale one gets 412 with the current record, so the UI
      can show what changed.
   7. **Long work** (an import, a statement read, a projection run, a reset copy) answers
      202 with a job resource (`/ui/api/jobs/{id}`: state, progress, result), and the live
      stream announces its end (§15.6).
   8. **Idempotency**: a `POST` that creates may carry `Idempotency-Key`; a repeat within 24
      hours returns the first answer. Imports are idempotent by their content (§4.3).
   9. **Versioning**: `/ui/api` is served with the app and changes with it, so it carries no
      version; the OpenAPI document states the release. `/mcp` and `/link` are versioned in
      their own protocol (G1, G7).
   10. **Visibility**: every read goes through the caller's shares (§13.3) and the soft-delete
       views (`schema.md` §4.2). A list never counts or hints at what the caller can't see.

# 17. Storage and secrets

1. **One SQLite database** (WAL) under the data directory, through SQLAlchemy, for everything
   but what links bring in, which lives in a SQLCipher database per link (§14.9). The schema
   follows [`schema.md`](schema.md), which a test enforces. The database is encrypted with
   **SQLCipher** under a key derived from the data key (§18.3), through the same
   `sqlcipher3` engine as linked copies.
   1. **Tables** are declared with SQLAlchemy Core (`Table`, `Column`) in `store/tables/`,
      one module per area, on one `MetaData`. A table module holds only columns, keys,
      constraints and indexes.
   2. **Entities** are plain dataclasses in `store/entities/` that import nothing from
      SQLAlchemy. `store/mapping.py` maps each one onto its table
      (`registry.map_imperatively`), relationships included. Business logic lives in the
      feature modules (`ledger/`, `loans/`, `giving/` and the others), and a test fails when
      their calculation code imports SQLAlchemy.
   3. **Revisions:** each change to the tables is a numbered Alembic revision, generated,
      reviewed by hand and committed, and a test fails when tables and revisions disagree.
      At start the server copies the database (verified) and then migrates it, one revision
      per transaction.
   4. **Access:** each table has a repository module. A unit of work is `Database.tx()`
      (`BEGIN IMMEDIATE`) or `Database.read()` (`PRAGMA query_only`, which refuses any
      write). Foreign keys are on, with a 10-second busy timeout.
   5. **Soft deletes**: records are never removed. Deleting one sets its `deleted`,
      `deletedAt` and `deletedById`, and each table's view works out whether a record is
      deleted through the records it belongs to. [`schema.md`](schema.md) (§4) sets the
      fields, the views and the few exceptions.
2. **Receipts** are files beside it (§12.2), owned by the server's account, mode 0600 in a
   0700 directory.
3. **Decimals**: money is stored as **integer cents**, and quantities and prices as **decimal text** validated to a fixed scale (18
   places, enough for wei), through a small SQLAlchemy column type. JSON carries both as
   strings. Python uses `decimal.Decimal` with a context of 34 digits and rounds `HALF_EVEN`
   except where a tax rule says otherwise. Floats are refused at the API's edge.
4. **Secrets** (price-source keys, the bitcoin node's credentials, the SMTP password, link
   private keys) are encrypted each on its own with AES-256-GCM under a data
   key of their own, wrapped under a key derived from the master key, with associated data
   naming the record
   and field, so a ciphertext copied onto another record fails to decrypt (§18.3). Secrets are
   decrypted only when used, never logged, and never sent back to the browser: the UI shows
   a stored secret as *set*, with when and by whom. Passwords and session, reset and
   invitation tokens are stored as hashes.
5. **The master key**: 128 random bits in a file on the host, outside the data directory and
   its backups, never in the database, backed up as a 12-word recovery phrase. §18 covers how it is made, protected, backed up,
   restored and rotated.
6. **Backups**: daily, verified, pruned, of the database **and the receipts directory**, to a
   directory set on the host; the time of day and the number of copies kept are Settings. The
   server makes, verifies (`PRAGMA integrity_check`) and prunes the copies itself. They are
   encrypted as the data is, and open with the master key's recovery phrase (§18.6). A
   restore is documented, and tested by a check. Linked copies (`links/`) are left out: they
   can't be checked without their access keys, and they are pulled again from their sources
   after a restore (§14.9.9).
7. **Financial data at rest** is encrypted with the rest of the database (§18.1). Ordinary SQLite tools can't read it. `moneykata db shell` opens it,
   as root on the host, with the key from the key file.
8. **Export**: a user can export their own data (accounts, transactions, lots, receipts) as a
   ZIP of CSVs and files, at any time. This is the way out, and the backup a single user can
   keep.
9. **Times and dates.**
   1. **Every timestamp is stored in UTC** (`deletedAt`, a session's start, an alert's
      opening, a price's `as_of`), and shown in the viewer's time zone.
   2. **Each user's time zone** is set in Profile: **Auto**, the server's time zone (from
      the host, shown in Settings › General), or a zone they choose by name
      (`America/Denver`).
   3. **Calendar dates have no time zone**: a transaction's date, a statement's period, a
      birthday and a due date are dates as the institution or the user wrote them, never
      shifted.
   4. **A trading day** is the US market's, in New York time: a daily close is dated by its
      market day, whatever the viewer's zone (§7.4).
   5. **"Today" for a user** follows their time zone: the year a tax year screen opens on,
      when an occasion's lead time starts, and the hour their daily summary email goes out
      (§15.11.5).
10. **Retention**: nothing is removed for at least **seven years**, the audit period: not
    records, soft-deleted records (`schema.md` §4), Activity, receipts or statements. How
    data older than that is retired is a later feature (G5). Backups keep their own, shorter
    retention (§17.6), and price history is kept for ever (§7.6).

# 18. Encryption and the master key

This section is for the admin who installs and runs the server. It explains what MoneyKata
encrypts and how, how to back up and protect the master key with its recovery phrase, and
what key rotation does.

1. **What is encrypted, and what is not.**
   1. **The database**: the whole main database, with SQLCipher, including the full text read
      from receipts and the thumbnails.
   2. **The receipt files**: each in its own encrypted file (§12.2).
   3. **Secrets, each on its own as well**: every *secret* the server holds so it can act for
      its users: price-source API keys, the bitcoin node's credentials, the SMTP password,
      and this server's private link key (§14.1).
   4. **Backups**, which are copies of the encrypted database and files (§17.6).
   5. **Encrypted under their own access keys, not the master key**: everything a link
      brings in, in its linked copy (§14.9). The master key cannot open it, so neither losing
      nor rotating the master key touches it.
   6. **Hashed, never encrypted**: passwords (argon2id) and session, invitation, reset and
      confirmation tokens (SHA-256 of a random value). They never need to be read back, so
      there is no key that could reveal them.
   7. **Not encrypted**: the configuration file, the logs, which must never hold amounts,
      names or secrets, and the key file itself (§18.4).
2. **No external key service.** MoneyKata keeps its master key in a file on the host.
   HashiCorp Vault, cloud KMSs (AWS, GCP, Azure), HSMs and TPM sealing are **not supported**.
   On a household server, an external service adds a dependency that must be running,
   backed up and secured itself, for little gain over a key file with good offline backups.
3. **How it works: three levels of keys.**
   1. **The master key**: 128 random bits in one file on the host (§18.4), made once at
      install. It is backed up as its **recovery phrase**: the same 128 bits written as 12
      words from the BIP39 English word list, the last word carrying a checksum. MoneyKata
      uses the words only as a way to write the key down. It never applies BIP39's wallet
      derivation to them. The master key encrypts one thing: the data key. It is never
      stored in the database, never written to a log, never sent over the network, never
      shown in the UI, and never included in the server's backups.
   2. **The data key**: 256 random bits, made at install, stored only **wrapped**
      (AES-256-GCM) under a key derived from the master key with HKDF-SHA256 (label
      `moneykata master`). The wrapped data key sits in the data directory (`keyring`), so it
      travels with every backup. From the data key, HKDF-SHA256 derives, each under its own
      label:
      1. the **database key**, which SQLCipher uses as its raw key;
      2. the **receipts key**, an X25519 key pair: receipt files use the streaming format of
         §14.9.6 with this key in place of a linked copy's key;
      3. the **secrets key**, which wraps the secrets' own data keys.
   3. **Secret data keys**: each secret gets its own random 256-bit data key when it is
      saved. The server encrypts the value with **AES-256-GCM** under it, using a random
      96-bit nonce. The **associated data** names where the secret belongs: record type, the
      record's stable id, and field. The secret's data key is then wrapped under the secrets
      key. The row stores the ciphertext, its nonce and the wrapped key.
   4. **Using a secret**: only when a task needs it (a price refresh, a bitcoin wallet read, an email). The
      server unwraps its data key, decrypts the value, uses it for that one call and discards
      it. GCM authenticates every step, so a tampered ciphertext, a wrong key, or a ciphertext
      copied onto another record or field fails to decrypt instead of producing a wrong value.
      Secrets are encrypted on their own as well as inside the database, so that a database
      opened for maintenance (§17.7) still shows no secret.
   5. **The master key id** is the first 16 hex digits of `SHA-256("moneykata key id" ‖ key)`.
      It identifies a key without revealing it. Its short form (`mk-3f9a…c21e`) is the
      **fingerprint** shown in Settings, on the recovery sheet and in the commands below. The
      wrapped data key records which master key wrapped it.
   6. **Why three levels**: rotating the master key re-wraps one 32-byte data key and nothing
      else; the database and the files never need re-encrypting for it; and each secret still
      stands or falls on its own, with associated data that stops anyone with write access to
      the database from moving one user's API key onto a record they control.
   7. **What a stolen copy gives away**: a copy of the data directory or a backup **without
      the master key** (the key file or its recovery phrase) reveals nothing but sizes and
      dates. With the key, it reveals everything in that copy. The key file sits on the
      host's own disk, so a stolen server disk holds both: that is why disk encryption on the
      host still matters (§18.6.7). An attacker who has root on the running server can read
      the key and the database, and no design changes that. This is why the key and the
      backups are kept apart (§18.6), and why §18.8 says to revoke secrets at their source
      when a key may have leaked.
4. **The key file.**
   1. **Where**: `/etc/moneykata/master.key` in the container, from a key directory on the
      host mounted there (§20.8), named in `moneykata.toml` under `[keys]`. It must be outside
      the data directory and outside the backup directory, so it never lands in a backup.
   2. **Owner and mode**: readable only by the server's account (uid 10001, mode `0400`).
      The running server mounts the key directory read only. There is no separate keys
      process. Never world- or group-readable, never writable by the server.
   3. **Made by** `moneykata keys init`, which writes 16 bytes from the operating
      system's random source with those modes, makes and wraps the data key, and refuses to
      overwrite an existing key. It then shows the **recovery phrase** and asks for three of
      its words back (§18.6.1). Until they are typed correctly, the key is not saved and the
      server cannot start.
   4. **Checked at start**: the server **refuses to start** (exit 78, §16.6) when the file is
      missing, is not exactly 16 bytes, can be written by anyone but root, can be read by
      anyone but its account, sits inside the data or backup directory, or does not unwrap
      the data key. `moneykata keys
      check` runs the same checks without starting the server.
   5. **Never** baked into the image, passed as an environment variable, or kept in a volume
      that is backed up with the data. A Docker secret works in place of the mounted
      directory.
   6. **Commands**, run on the host as one-off containers of the same image (`docker compose
      run --rm moneykata keys verify`); only `init` and `rotate` mount the key directory
      writable, and only `rotate` mounts `moneykata.toml` writable, to record the previous
      key in it. `rotate` checks it can write all three before it changes anything. Nothing an admin does day to day: `moneykata keys init`,
      `check`, `fingerprint`, `phrase` (shows the recovery phrase again), `verify` and
      `rotate` (§18.6, §18.7), and `moneykata db shell` (§17.7).
5. **What losing it costs.** Everything this server holds is encrypted under the master
   key, so **losing both the key file and its recovery phrase loses all of it**: the
   database, the receipts and every backup. There is no back door, and no one can recover
   it, including the people who make MoneyKata.
   1. **The key file lost, the phrase kept** (a failed disk, a rebuilt host): write the key
      back from the phrase with `moneykata keys init --from-phrase` and restore. Nothing
      is lost.
   2. **The phrase lost, the key file kept**: nothing is lost yet, but the next failure will
      be. Show the phrase again with `moneykata keys phrase` and back it up at once, or
      rotate the key (§18.7) and back up the new phrase.
   3. Linked copies are not affected either way: they open with their own access keys, and
      are pulled again from their sources (§14.9.9).
6. **Backing up and protecting the master key.**
   1. **Back it up as it is made.** `keys init` and `keys rotate` show the **recovery
      phrase**, 12 numbered words, with the fingerprint, the server's name and the date, and
      will not finish until three words chosen at random are typed back. `moneykata keys
      phrase` shows it again at any time, and `--file PATH` writes it as a recovery sheet to
      print. Each word is recognised by its first four letters, and the last word's checksum
      catches most mistakes when the phrase is typed back in.
   2. **Keep at least two copies in two places**, at least one of them offline. For example:
      1. the printed sheet in a fire-resistant safe at home or a bank safe-deposit box;
      2. a secure note in the household's password manager (Bitwarden, 1Password, KeePassXC),
         in a vault that the second person below can also open;
      3. optionally, a USB stick holding the export encrypted with a passphrase (`age -p` or
         `gpg -c`), stored apart from the first copy.
   3. **Never keep it with the database backups**: not in the same directory, on the same
      disk, in the same cloud bucket, or in the same archive. A backup that holds both the
      database and the key protects nothing.
   4. **Never put it** in git, a ticket, a chat message, email, a shared drive, a container
      image, or a screenshot.
   5. **Check the backup.** `moneykata keys verify` asks for the whole phrase and says
      whether it matches the running key, without changing anything. Settings › Key storage
      records each confirmation: who, which fingerprint, and when. Check the copies once a
      year: that the sheet is readable, and that the password manager entry still verifies.
      Settings reminds admins when a year has passed.
   6. **Two people should be able to recover it**: the admin and one trusted person, such as a
      partner, an executor or an adult child. Write down where the copies are, alongside the
      household's estate documents, because financial records are needed exactly when the
      person who set up the server is not available.
   7. **Protect the host as well**: full-disk encryption on the server (LUKS, FileVault,
      BitLocker or ZFS native encryption), because the key file sits on the same disk as the
      data, and root access limited to the people who run the server. Backups are already
      encrypted, so they can go to a NAS or a cloud bucket as they are, as long as the
      recovery phrase never goes with them.
   8. **Restoring onto a new host**: install MoneyKata, write the key from the recovery
      phrase with `moneykata keys init --from-phrase` (which checks the checksum and,
      given the backup, the fingerprint, and sets the owner and mode), restore the data
      directory from the backup, and start. At start the server unwraps the data key, opens
      the database, and reports anything it cannot open. `operations.md` has the step-by-step runbook, and a check rehearses
      it.
7. **Key rotation.** There are two kinds, and they do different things.
   1. **Rotating the master key** replaces the key file and its recovery phrase, and
      re-wraps the data key under the new key. Nothing else is re-encrypted. It is done on
      the host:
      1. `moneykata keys rotate` makes a new key, shows its recovery phrase and asks for
         three words back, re-wraps the data key in one step, and moves the current key to
         the `previous` list in `moneykata.toml` (with its fingerprint);
      2. **back up the new phrase at once** (§18.6), then restart the server;
      3. verify the new phrase (`keys verify`);
      4. **keep the previous key until every backup made before the rotation has been
         pruned** (the backup retention, §17.6, is 14 days by default), because those
         backups hold the data key wrapped under it. Then remove it from `previous`, delete
         the old key file, and destroy its recovery sheet and password-manager entry.
         Settings names the date after which the previous key is no longer needed.
   2. **Re-encrypting** (Settings › Key storage › **Re-encrypt**, admins) makes a new data
      key: the database is re-keyed (`PRAGMA rekey`), receipt files are re-encrypted a few
      at a time while the server keeps serving, and every secret gets a fresh data key and
      nonce. The master key is unchanged. Settings › Key storage shows the progress. It is
      rarely needed: only when the data key may have been exposed, such as a memory dump or
      a debugging session on the live server.
   3. **What rotation does not do**:
      1. It does not change the secrets themselves. A price source's API key is the same key after
         rotation, and anyone who already read it can still use it.
      2. It does not protect copies made before it. A backup taken before a master-key
         rotation can still be opened with the old key, which is why the old key is
         destroyed once those backups are gone.
      3. It does not touch passwords, which are hashed, or linked copies, which have their
         own access keys.
   4. **Rotation is recorded** in Activity for admins: who, when, and the old and new
      fingerprints. Key material is never recorded.
8. **Best practices for rotation.**
   1. **Rotate the master key when there is a reason**:
      1. someone who had root on the server, or held a copy of the key, no longer should;
      2. a copy of the key may have been exposed: a lost recovery sheet, a compromised
         password-manager vault, a disk with the key file sold, recycled or lost;
      3. the server was compromised (and after rebuilding it).
   2. **Otherwise, rotate on a calm schedule: once a year is plenty** for a household server.
      Every rotation means a new backup of the key in two places and an old one to destroy
      later. Rotating more often adds that work and the risk of a key with no backup, without
      adding security. Settings shows the key's age and reminds admins after a
      configurable period (12 months by default; off is allowed).
   3. **When a key may have leaked, rotation is the second step, not the first.** First
      **revoke and reissue the secrets at their source**: new price-source keys, a new
      password for the bitcoin node, a new SMTP password. Then rotate the master key, so
      future copies are wrapped under a key nobody else has. Rotation alone leaves every
      secret readable from any old copy.
   4. **Never rotate without a tested backup of the new key.** Rotate when there is time to
      make and verify the backups the same day, not at the end of a maintenance window.
   5. **Keep the previous key exactly as long as the backups that need it**, then destroy every
      copy of it. A previous key kept for ever is a second key to protect.
   6. **Re-encrypt** only for its specific reason (§18.7.2). It is not a substitute for
      rotating the master key, or for revoking a leaked secret.

# 19. Settings (admins)

One screen with a section list on the left, **General first** and selected when Settings
opens. Each section has its own help guide. In this order:

1. **General**: server name (shown to linked servers), the **household name and avatar** (an
   image, or initials; shown at the top of the sidebar here, and sent to linked servers,
   which always show them as set here, §15.10), public URL (links in emails are built from
   it, never from the request), and the server's time zone, read from the host (§17.9).
2. **Email (SMTP)**: host, port, security, username, password (a secret), from address, and
   **Send a test email**.
3. **Sign-in and sessions**: idle and absolute session lifetimes, lockout after failed
   sign-ins.
4. **Sign-up**: on or off (it needs SMTP), optionally limited to email domains.
5. **Passwords**: the minimum length (12 by default, at least 8).
6. **Prices** (§7.2.3): the enabled sources with their classes, keys, order, last run and
   error; **Add a source**; and the time of the daily refresh (6:00 PM Eastern by default).
7. **Bitcoin** (§4.6): the explorer or node for self-custody wallets: a public Esplora
   (mempool.space by default) or the household's own node, with its address, credentials and
   a **Test** button.
8. **Imports** (§4.3): the file types and size accepted for statement import, and whether
   statements are read on the server (sharing the receipt reader's jobs, §12.8).
9. **Linked servers** (§14.7): the links, and each linked copy's state: changes waiting, its
   access key (*Create the access key*, made when and by whom), locked or unlocked (by whom,
   and when it will lock), *Lock now* and *Reset copy*, and **Release linked keys after**
   (one hour unused by default).
10. **Receipts**: the size limit and allowed types; **Read receipts** on or off, jobs at a
    time, the reading queue, and **Re-read all receipts** (§12.8.7).
11. **Tax tables**: per year, shipped and correctable: contribution limits and thresholds,
    the annual gift exclusion, the 529-to-Roth lifetime limit, the QCD limit, the
    collectables rate, the shipped college-cost averages (§9.2.2), the bitcoin models'
    published figures (§9.3.1), and the metal per share of SLV, PPLT and PALL (§7.3).
12. **Backups**: the time of day and the copies kept; the backup directory is set on the host.
13. **Key storage** (§18): read-only. The master key's fingerprint and age, who confirmed
    its recovery phrase and when, rotation progress and the date the previous key can go, the
    progress of a re-encryption, and anything that cannot be opened. Buttons: **Test** and
    **Re-encrypt**. The master key itself is only ever changed on the host.
14. **Network**: address ranges allowed to `/ui` and to `/link`.
15. **TLS** (in `tls` mode): the listener's certificate and key.
16. **Alerts** (§15.11): how long a source may fail before it raises an alert (48 hours
    by default), and the time of the daily summary email (07:00 by default, in each user's
    time zone).

# 20. Implementation

1. **Layout**:

   ```
   README.md
   docs/                 requirements.md (this), schema.md, api.md, link-protocol.md,
                         operations.md, mockups/MoneyKata-mock.html
   web/
     VERSION  dev.sh  check  pins
     ui/                 index.html, deno.json, app/{main,router,config,hooks,format}.js,
                         api/, store/, screens/, components/, charts/ (the chart wrappers),
                         account-types/ (one module per type: fields, icon, help),
                         styles/{tokens,base,components}.css, assets/icons.svg,
                         guides/, vendor/, tests/, mockup/
     server/             src/moneykata/: main.py, app.py, config.py, listener.py, middleware.py,
                         static.py, settings.py, ui/ (routes per area), auth/, store/
                         (tables/, entities/, mapping.py, alembic/), ledger/ (lots, gains, wash sales, corporate
                         actions), prices/ (one TickerSource per source), bitcoin/ (esplora,
                         electrum, core), importers/ (ofx, csv, statements), budgets/, projections/, loans/
                         (schedules, payoff planner), assets/ (items, valuations),
                         gifts/ (people, occasions, holiday tables), giving/,
                         taxes/ (8949, txf, limits tables), receipts/ (storage, thumbnails,
                         ocr/: worker, parser, models/), links/, mail/, dev/
     install/            Dockerfile, compose.yaml, moneykata.toml, reverse-proxy examples
   ```

2. **Server dependencies**, each a ruling, kept short because each runs with the database: fastapi, pydantic,
   hypercorn, sqlalchemy, alembic, argon2-cffi, cryptography (AES-GCM, Ed25519 for links),
   httpx, segno (two-step QR), **Pillow** and **pypdfium2** (thumbnails and receipt reading,
   §12.5, §12.8), **sqlcipher3** (the wheel that bundles SQLCipher, for linked copies,
   §14.9), **rapidocr** with **onnxruntime** (receipt reading, §12.8). rapidocr brings
   numpy, opencv-python-headless, shapely, pyclipper and pyyaml with it, about 100 MB in all;
   the image carries them, and they load only in the receipt worker. **ofxtools** reads OFX
   and QFX files (pure Python, GPL-3.0-only, compatible with MoneyKata's GPLv3). **pi-heif** reads iPhone photos
   (HEIC): it decodes only, so it is smaller than pillow-heif, which also encodes. **numpy** is a direct dependency for projections
   (§9) as well as RapidOCR's.
   Standard library for email (`smtplib`), config (`tomllib`), logging and the command line.
   Pinned exactly in `uv.lock`, Python 3.12.
3. **The browser app: no build step.** The files in `web/ui` are the files the browser loads.
   1. **Libraries**: Preact (rendering), HTM (JSX-like tagged templates, no `eval`),
      @preact/signals (state), preact-iso (routes and lazy screens), plus the chart library
      (§20.4). Each is **vendored**: its npm tarball is committed under `web/ui/vendor/`,
      named with its exact version in `manifest.json`, and `vendor.py extract` unpacks the
      files the import map points at. No npm, no network at install.
   2. **An import map** in `index.html` resolves `import 'preact'` to the vendored file.
      JavaScript with JSDoc types, type-checked by Deno. No minification and no source maps,
      so a stack trace names a file in the repository.
   3. **Strict Content Security Policy**: `script-src 'self' 'nonce-…'` (the nonce covers only
      the import map), `style-src 'self'`, no inline scripts or styles, no `eval`. No
      third-party requests: no CDN, no web fonts, no analytics.
   4. **Size budget**: under 150 KB compressed for the first screen; every other screen is a
      module loaded by a native `import()` on first visit.
   5. **Cache-busting**: the app is served under `/ui/v/<version>/` with a one-year cache;
      `index.html`, templated with the version and the nonce, is `no-store`.
   6. **Plain CSS** with custom properties and `@layer`: `tokens.css` (colours and sizes, dark
      first), `base.css`, `components.css`. Icons are one SVG sprite.
   7. **The server is the only state.** The browser remembers only how the page looks: theme,
      sidebar, help pane, page size, privacy mode.
   8. Current Chrome, Edge, Safari and Firefox; no polyfills.
4. **Charts.** The constraints come from §20.3: an ES module the import map can point
   at, vendored with no bundler, working under `script-src 'self'` and `style-src 'self'`
   with no `eval` and no injected `<style>`, colours from `tokens.css`, both themes, and a
   size that is fine if it loads only with the chart screens. Three candidates are worth
   considering:

   | | **Apache ECharts** 5/6 (Apache-2.0) | **uPlot** (MIT) | **Lightweight Charts** (TradingView, Apache-2.0) |
   | --- | --- | --- | --- |
   | Size (gzip) | ~330 KB full ESM build; ~150 KB hand-picked, but picking needs a bundler, so we'd vendor the full file | ~20 KB | ~45 KB |
   | Charts we need | **all**: line/area with range zoom, donut, **treemap**, **Sankey** (cash flow), candlesticks, stacked bars, Monte Carlo fan (stacked bands), markers | line/area/bars, bands for the fan, markers; **no** donut, treemap or Sankey: we'd draw those as our own SVG | financial time series only: line, area, candles, histogram, markers for trades; **no** donut, treemap, Sankey, fan |
   | Rendering | canvas or **SVG** (switchable; SVG suits theming and print) | canvas | canvas |
   | Performance | good to ~100k points | best by far: millions of points | very good, built for price series |
   | Theming | registered themes, built from our CSS variables at run time | CSS file plus options | options |
   | CSP | clean (sets inline styles only through the DOM, which `style-src` allows) | clean; ships its own CSS file, served as ours | clean |
   | Accessibility | ARIA description generation built in | none | none |
   | Catch | size; a large API surface | we write and maintain the non-time-series charts | **requires a TradingView attribution link on the chart**; only covers prices |

   **Apache ECharts**, lazily imported by the chart screens through a small
   `app/charts/` wrapper (theme from tokens, table-view toggle, number formatting). Sign-in and
   the first screen's budget (§20.3.4: under 150 KB) stay unaffected. It is the only one
   of the three that covers every chart in §8–§10 without code of our own. **uPlot** is the
   choice if size and a minimal surface matter more than coverage, at the cost of a few
   hundred lines of our own SVG for donut, treemap and Sankey. **Lightweight Charts** is
   best kept as a possible *addition* for the holding-detail price chart, not the base.
   Chart.js (MIT, ~70 KB) was considered: it is wide enough except for treemap and Sankey
   (plugins), but its time axis needs a separate date-adapter dependency and its ESM build
   imports a further package. It offers less than ECharts for little size saved.

   The mockup draws its charts with small hand-written SVG functions, so it stays one small
   file and doesn't pre-empt this choice.
5. **Tests and checks**, all run by `web/check`, with no Node.js: pytest with a throwaway SQLite per test (most of the
   weight: lots, gains, wash sales, option assignment, imports, budgets, projections, sharing,
   links), browser component tests in headless Chromium driven by Playwright for Python, Deno
   check/lint/fmt, ruff, OpenAPI and typedef drift, mockup drift and the help-guide checks.
   Browser tests use a small in-page runner (`web/ui/tests/run.js`) and a fake API; one
   smoke test drives a running dev server. **Golden files**: a fixture portfolio with known
   8949 rows and TXF output, checked byte for byte. **Receipt reading**: the field parser is
   tested on OCR text, and a set of fixture receipts (phone photos, flatbed scans, text-layer
   PDFs; skewed, faded, rotated) runs through the real RapidOCR worker against expected date,
   total and merchant, with an accuracy floor that a change must not drop below.
6. **`web/dev.sh`** is the developer's front door: alone it prints its commands (`setup`,
   `run`, `test`, `check`, `mail`, `mockup`, `help-shots`, `deno`). `web/pins` holds the
   versions and hashes of the dev-only downloads (Deno, Playwright's Chromium).
7. **Dev mode** (`web/dev.sh run --seed --stubs`, `moneykata dev`) runs the whole server from a
   checkout as the current user, relaxing the surroundings, never the rules: sessions, CSP,
   encryption and sharing behave as in production. `https://localhost:37373` with a
   self-signed certificate, `web/.dev/` for data, receipts and mail, seed users
   (`admin`, `alice`, `bob`, a *Household* group), a year of seeded transactions across every
   account type, open and closed option positions with an assignment and a wash sale, budgets,
   two projections, receipts, and a **stub price source** (deterministic random walks,
   `--stubs`). A second dev server on another port with `--peer` lets links be exercised on
   one machine. Emails are written to `web/.dev/mail/` and their links printed. A red **DEV**
   pill shows on every screen. For testing from another machine, `--listen` sets the address
   it listens on and each `--hostname` adds a name (or address) to its certificate, which is
   made again when it doesn't cover them all; `web/dev.md` describes the setups. Dev mode
   refuses to run as root or on an installed server's
   data directory, and never calls a real provider unless one is configured.
8. **Packaging: one Docker (OCI) image** holding its own Python and venv, the browser app,
   RapidOCR's models and the `moneykata` command, running as an unprivileged user (uid
   10001). It serves on port 37373 and takes three mounts: the **data directory** (database,
   receipts, linked copies), the **backup directory**, and the **key directory**, read only
   for the server and kept out of the backups (§18.4). `moneykata.toml` is mounted too;
   secrets never come from environment variables. `install/compose.yaml` is the example to
   start from.
   1. **Architectures**: one multi-architecture image for **amd64** and **arm64**, both built
      on an amd64 build server with `docker buildx` (arm64 under QEMU emulation). Every
      dependency must install from a published wheel for both (onnxruntime, opencv, numpy,
      pi-heif, sqlcipher3 among them), since compiling under emulation is too slow; a check
      fails when one has no arm64 wheel.
   2. **No registry.** The image is built locally and carried to its host (`docker save` and
      `docker load`), or built on the host itself.
   3. **Documented hosts**: **Proxmox** (Docker in a VM, or in an LXC container with nesting
      on) and **TrueNAS** (a custom app from the compose file). `operations.md` covers
      both: mounts, the key directory, backups and upgrades.
   4. **TLS**: the example `compose.yaml` runs in `proxy` mode behind the household's
      reverse proxy. A second example runs `tls` mode with a self-signed certificate for
      testing on a local network (§16.3).
9. **Milestones** *(proposed)*. The requirements describe the finished product; this is the
   order to build it in. Each milestone ends with `web/check` passing, a Docker image that
   runs, and the generated mockup covering what was built.
   1. **Milestone 1, the foundation and one household's accounts:**
      1. **Repository and tooling**: the layout of §20.1, `web/dev.sh`, `web/check`
         (pytest, ruff, Deno, Playwright, OpenAPI and typedef drift), `uv.lock`, and the
         Docker image for amd64 and arm64 with `compose.yaml` (§20.8).
      2. **Server core**: configuration, the listener in both modes (§16.3), the refused
         start (§16.6), the security policies (§16.7), the API conventions (§16.8), the live
         stream (§15.6), background tasks (§16.4) and dev mode with seed data (§20.7).
      3. **Storage and keys**: the SQLCipher database, the master key with its recovery
         phrase, `keys` commands and data key (§18), Alembic, the schema conventions with
         prefixed ids, soft-delete fields and `<Table>Effective` views, and the schema
         checks (`schema.md`); backups (§17.6).
      4. **Users**: the default admin's setup, invitations (email written to a folder until
         SMTP is set), sign-in, sessions, password reset, the active flag, groups, and
         Profile (time zone, theme). Two-step sign-in can wait for milestone 2.
      5. **Accounts and transactions**: account types for banking, cards, brokerage and
         retirement (§4.1, without loans, 529s, physical assets or crypto); manual entry,
         CSV and OFX/QFX import (§4.3.1–4.3.2); transactions with categories; holdings and
         lots from brokers' files (§5); transfers matched (§4.7); reconciliation's coverage
         and anchors (§4.11).
      6. **Prices**: the `TickerSource` interface with Tiingo, Coinbase, manual and the dev
         stub (§7), the daily refresh, stored closes and staleness.
      7. **Sharing between users**: accounts and portfolios, read and write, users and
         groups (§13.3–13.7), and Activity (§13.8).
      8. **The app**: the frame, navigation, help pane with its guides, theme and privacy
         mode (§15); Dashboard (net worth, accounts, needs attention), Accounts, an account's
         Overview, Transactions and Reconcile, the Transactions screen, Portfolios with
         Performance and Holdings, Settings (General, Sign-in and sessions, Passwords,
         Prices, Imports, Backups, Key storage) and Users and Groups.
      9. **The mockup** generated from the app for these screens (§15.9); the hand-written
         mockup stays the reference for everything not built yet.
   2. **Milestone 2**: two-step sign-in, SMTP and emails, Alerts, budgets, receipts with
      reading (§12), statement import (§4.3.3, G8), projections and assumptions (§9).
   3. **Milestone 3**: taxes and tax books (§11), loans and the payoff planner, 529s,
      physical assets, gifts and giving.
   4. **Milestone 4**: positions and options (§6), bitcoin wallets and own node (§4.6, G9),
      the MCP endpoint (§13.9).
   5. **Milestone 5**: linked servers and linked households (§14, §15.10, G1).

# 21. Open questions

None at present. A question raised later is added here, and removed once its answer is
written into the section it belongs to.

# 22. Gaps

Areas the requirements name but don't yet specify. Each keeps its id for good: a gap that is
closed is removed, and its id is not used again.

| Id | Gap | What is missing | Touches |
|---|---|---|---|
| **G1** | Link protocol and version skew | `docs/link-protocol.md`: the messages, their signing, and what two linked servers on different MoneyKata versions do | §14 |
| **G2** | Web security in one place | the policies of §16.7 are proposed and await review | §16, §17 |
| **G5** | Data sunset | how data older than the seven-year audit period is retired: what goes, what is summarised, who decides, and how it is confirmed (§17.10) | §17, `schema.md` §4 |
| **G6** | Operations | `docs/operations.md`: upgrades and migrations in the Docker image, health checks, logs, monitoring, restore drills | §16, §18, §20.8 |
| **G7** | API conventions and reference | the conventions of §16.8 are proposed and await review; `docs/api.md` grows with the code, beside the generated OpenAPI, and documents the MCP tools | §13.9, §16, §20.5 |
| **G8** | Statement import | how statement layouts are found in PDFs and photos, what is kept per institution, multi-page and multi-account statements, and card and brokerage statements | §4.3 |
| **G9** | Bitcoin node integration | the details of each node kind (Esplora, Electrum server, Bitcoin Core watch-only descriptors), xpub gap limits, and testing a node | §4.6 |

# 23. Not in scope

Foreign accounts, and currencies other than the US dollar. Coins and chains other than
bitcoin, and reading crypto exchanges through their APIs (later). Deleting a user and their data: a
user who leaves is made inactive. Trading, order entry or any write
to an institution. Real-time quotes and greeks. Bill
payment, including making loan payments. Automatic valuations of homes, vehicles or
collectables (values are typed or appraised). Refinancing or payoff advice: the payoff
planner compares, and does not recommend. Shopping, wish-list or registry services for
gifts. State 529 deduction rules. Tax filing or tax computation. Running a relay for links. Phone support in the web app: a
mobile PWA with a narrower, focused set of features comes later, as its own piece of work.
Storing the private keys or seed phrases of crypto wallets, ever (MoneyKata's own recovery
phrases are words for its keys, not wallets). Opting users in or out of the list a server
sends its linked peers (§13.3.3): every active user is listed, which suits a household; a
server for more people would need it.

# 24. Rejected ideas

Ideas that were weighed and turned down, kept so they are not raised again without a new
reason.

1. **A separate keys process** that alone reads the master key and wraps and unwraps keys over
   a Unix socket. A compromised web process could then not copy the key, but it costs a
   second account and a socket, and the web process can already read everything the key
   protects while it runs. The server's own account reads the key file (§18.4).
2. **External key services** (HashiCorp Vault, cloud KMSs, HSMs, TPM sealing): another
   service to run, back up and secure, for little gain over a key file with offline backups
   (§18.2).
3. **Leaving the financial data unencrypted** and relying on disk encryption and encrypted
   backups. Backups leave the house, so the database and receipts are encrypted by MoneyKata
   (§18.1).
4. **The master key written as base32** on a recovery sheet. Twelve BIP39 words are easier
   to write down, read back and type, and catch typos better (§18.6.1).
5. **A personal access key per user for linked copies**, with the copy key sealed to each
   user (by a passphrase of their own, or by their password). The owner's shares already
   decide who sees what, so the key only has to protect the copy at rest. One key per copy,
   unlocked for the server, is simpler and recovers more easily (§14.9.3).
6. **The receiving admin choosing who sees each linked share.** Servers exchange their user
   lists, so the owner names the people (§14.3).
7. **Linked accounts shown among this household's own**, as locked rows, in totals or inside
   local portfolios. Another household's data is a world of its own and opens in its own
   window (§15.10).
8. **SQLModel** for the tables. It merges the table, the API model and the entity into one
   class. Tables are declared with SQLAlchemy Core and mapped onto plain dataclasses, so the
   schema carries no logic (§17.1).
9. **A portfolio showing an account its viewer can't see** as one line with its value. It
   still discloses a figure the owner didn't share; viewers see only what is shared with
   them, and the Share dialog offers to share the rest (§8.1).
10. **Write access for agents.** An agent reads through a token and can never change
    anything, whatever shares its user holds (§13.9).
11. **An RPM** with its own Python, beside or in place of the Docker image. A home server is
    far more often a NAS, a Raspberry Pi or a container host than a RHEL machine (§20.8).
12. **Barchart** for prices. Its website's terms forbid robots, data mining and applications
    built on it without written consent, and its API (OnDemand) is a paid commercial
    product (§7.1).
13. **Stooq** as the no-key source for daily prices and metals spot. Since 2026 its downloads
    need a key obtained through a captcha, with a daily quota, which a server can't keep up
    (§7.3).
14. **Yahoo Finance** (unofficial). It has no API terms and breaks without notice.
15. **Bank aggregation** (SimpleFIN Bridge and the like). It costs each user a subscription
    and gives a third party standing read access to their accounts. Statements and exports
    the user downloads cover the same ground (§4.3).
