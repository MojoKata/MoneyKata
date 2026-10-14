# MoneyKata: requirements

Status: **DRAFT** 2026-10-10. MoneyKata is a self-hosted **personal finance server** for a
household or a small group of people. It holds their accounts (bank, brokerage, crypto
exchange, self-custody wallets, IRA, Roth IRA, 401(k)), tracks holdings and positions (options
included), charts portfolios, projects future value, keeps budgets and receipts, and prepares
the numbers a tax return needs. Several people use one server. They share accounts and
portfolios with each other, read-only or read/write, and share read-only with people on
**other MoneyKata servers** on other LANs.

**How the requirements are organised.** This file holds what applies everywhere: the
decisions (R1), the terminology (R2) and the design principles (R3). Each subject has its own
section file, S1 to S17, listed below. A reference names a part by its id and number:
`R1.16` is item 16 of the decisions here, `S9.8.7` item 8.7 of the receipts section, `G8` a
gap and `Q8` an open question.

1. **Lasting ids.** Section ids (S1, S2, …) and their first-level items (`S1.2`) are never
   renumbered or reused: a new section or first-level item takes the next free number, and
   one that is removed leaves its number unused. Deeper items may be renumbered, with every
   reference updated in the same change. Gaps (G) and questions (Q) keep their ids the same
   way.
2. **Splitting a section.** A section file that grows past 500 lines moves its first-level
   items to files of their own, named by the item's number (`S1-accounts-02-brokerage.md`
   holds S1.2), and keeps a summary with a table of them in the form of the one below.
   References do not change.
3. **A statement, not a changelog.** The requirements say what MoneyKata is and does, in the
   present tense; git holds their history.

**Mockup:** [`../mockups/MoneyKata-mock.html`](../mockups/MoneyKata-mock.html) is the
clickable mockup. It is one file that opens from disk and sends nothing anywhere. It is
hand-written, and alongside it a second mockup is generated from the app for the screens built
so far (S12.9). Its purple **MOCK** pill jumps to any screen, switches between users, and
opens the dialogs.

## Sections

| Id | Section | What it covers |
|---|---|---|
| **S1** | [Accounts](S1-accounts.md) | Account types, how accounts are kept current (manual entry, CSV, OFX, statements, bitcoin watch), retirement, crypto, 529s, loans, physical assets, transfers and reconciliation |
| **S2** | [Holdings, lots and transactions](S2-holdings-and-lots.md) | Instruments, lots and their cost basis, corporate actions and payee rules |
| **S3** | [Positions and options](S3-positions-and-options.md) | Positions, option contracts and their lifecycle |
| **S4** | [Prices](S4-prices.md) | Free daily prices: the sources per asset class, the daily refresh, stored closes and staleness |
| **S5** | [Portfolios and charts](S5-portfolios-and-charts.md) | Portfolios across accounts, performance, allocation and the charts |
| **S6** | [Projections](S6-projections.md) | Goals (retirement, education, savings), assumptions, the models, scenarios, active plans and the loan payoff planner |
| **S7** | [Budgets, gifts and giving](S7-budgets-gifts-and-giving.md) | Budgets and categories, recurring transactions, people and occasions, gifts and charitable giving |
| **S8** | [Taxes](S8-taxes.md) | Tax books, tax documents, what a return needs, and the tax tables |
| **S9** | [Receipts](S9-receipts.md) | Upload, encrypted storage, viewing, links, sharing, retention and reading receipts on the server |
| **S10** | [Users, groups and sharing](S10-users-and-sharing.md) | Users, sign-in, groups, what can be shared and how, Activity and the MCP endpoint |
| **S11** | [Linked servers](S11-linked-servers.md) | Read-only sharing between households on separate MoneyKata servers |
| **S12** | [Web UI](S12-web-ui.md) | The frame, navigation, screens, help pane, live updates, linked households' windows and Alerts |
| **S13** | [Architecture](S13-architecture.md) | The listener and its modes, background tasks, the egress guard, the refused start, security policies and API conventions |
| **S14** | [Storage and secrets](S14-storage-and-secrets.md) | The database, files, secrets, backups, time zones and retention |
| **S15** | [Encryption and the master key](S15-encryption-and-master-key.md) | The master key and its recovery phrase, the data key, rotation and recovery, for the admin who runs the server |
| **S16** | [Settings (admins)](S16-settings.md) | Every section of the Settings screen |
| **S17** | [Implementation](S17-implementation.md) | The stack, the repository layout, checks, dev mode, the Docker image and the milestones |

## Gaps

Areas named but not yet specified ([gaps.md](gaps.md)).

| Id | Gap | What is missing |
|---|---|---|
| **G1** | [Link protocol and version skew](gaps.md#g1-link-protocol-and-version-skew) | `docs/link-protocol.md`: the messages, their signing, and what two linked servers on different MoneyKata versions do |
| **G2** | [Web security in one place](gaps.md#g2-web-security-in-one-place) | the policies of S13.7 are proposed and await review |
| **G5** | [Data sunset](gaps.md#g5-data-sunset) | how data older than the seven-year audit period is retired: what goes, what is summarised, who decides, and how it is confirmed (S14.10) |
| **G6** | [Operations](gaps.md#g6-operations) | `docs/operations.md`: upgrades and migrations in the Docker image, health checks, logs, monitoring, restore drills |
| **G7** | [API conventions and reference](gaps.md#g7-api-conventions-and-reference) | the conventions of S13.8 are proposed and await review; `docs/api.md` grows with the code, beside the generated OpenAPI, and documents the MCP tools |
| **G8** | [Statement import beyond bank and card statements](gaps.md#g8-statement-import-beyond-bank-and-card-statements) | brokerage statements, statements of several accounts, and learning column positions for layouts without sections or a running balance |
| **G9** | [Bitcoin node integration](gaps.md#g9-bitcoin-node-integration) | the details of each node kind (Esplora, Electrum server, Bitcoin Core watch-only descriptors), xpub gap limits, and testing a node |
| **G10** | [Statement intervals per account](gaps.md#g10-statement-intervals-per-account) | the interval each account's statements are expected at, how it is set or learned, and the alert threshold that follows |
| **G11** | [Wash-sale basis carried into holdings](gaps.md#g11-wash-sale-basis-carried-into-holdings) | the replacement lot's adjusted basis and holding period in Holdings and its later sale |

## Also here

- [Open questions](questions.md): what waits on a decision.
- [Out of scope](out-of-scope.md): what MoneyKata does not do.
- [Rejected ideas](rejected-ideas.md): ideas weighed and turned down, with the reason.

# R1. Decisions

The rulings the rest of the requirements apply. Rulings marked *(proposed)* are
recommendations waiting for a decision.

1. **The stack** (S17): a Python server (FastAPI under Hypercorn), SQLite through
   **SQLAlchemy** with **Alembic** migrations, and a browser app with **no build step** (Preact,
   HTM, @preact/signals, preact-iso, vendored and pinned, loaded as plain ES modules under a
   strict CSP). There is **no Node.js anywhere**. Deno type-checks and lints, and Playwright for
   Python runs the browser tests.
2. **A single-page app at `/ui`**, dark-mode first, in one frame: a collapsible
   sidebar, the signed-in user at its foot, the theme button, a DEV pill in dev mode and an
   update pill. It is built for desktop browsers. Phones will get a separate, focused PWA
   later, not the whole web app (S12.8, [out of scope](out-of-scope.md)).
3. **Context-sensitive help on every screen**: the F1 help pane, with one Markdown guide per
   screen or panel that follows the focused field (S12.7). A test fails when a field has
   no heading in its guide.
4. **A clickable mockup** in `docs/mockups/`, opened from disk. It shows every screen and
   dialog on sample data, and its MOCK pill drives it (S12.9).
5. **A dev mode, `moneykata dev`**, runs the whole server from a checkout as the current user.
   It uses a self-signed certificate, writes emails to a folder, uses canned price feeds and
   seed data, and keeps every rule as strict as production (S17.7).
6. **Users, groups, invitations, sign-up approval, two-step sign-in and deactivation**
   (S10.1). An admin's extra powers are managing users and groups and the server's
   Settings. **Admins cannot see other users' money** unless it is shared with them (S10.2).
7. **Users own accounts.** Any user can create accounts and portfolios and share them with
   users or groups, **read** or **read/write** (S10).
8. **Linked servers.** Two MoneyKata servers on different LANs can be linked. A link carries
   **read-only** shares of accounts and portfolios one way, and is never read/write (S11).
9. **Money is never a float.** Amounts and quantities are decimals end to end: `Decimal` in
   Python, strings in JSON, and integers or decimal text in SQLite (S14.3).
10. **Prices are delayed, never live.** MoneyKata is not a trading app. It reads end-of-day
    closes from free sources, through pluggable **price sources** (S4).
11. **Read-only by construction toward institutions.** MoneyKata never moves money, places an
    order or signs a transaction. It never stores a self-custody wallet's private key or seed
    phrase, only public addresses or extended public keys (S1.6).
12. **Receipts are files on the server**, PDF or image, uploaded from the browser and attached
    to transactions, tax items or nothing (S9).
13. **Everything the server stores is encrypted at rest**: the database
    (SQLCipher), the receipt files, and each secret on its own. All of it opens with one
    **master key**, kept in a file on the host outside the database and its backups, and
    backed up as a **12-word recovery phrase** (S15). The server's own account reads the key
    file. There is no separate keys process, and **no Vault or other external key service**
    (S15.2).
14. **Charts: Apache ECharts**, vendored and loaded only by the screens that draw charts
    (S17.4).
15. **The code lives in `web/`**: `web/ui` (the browser app) and `web/server` (the Python
    package `moneykata`). The docs are in `docs/` (S17.1).
16. **MoneyKata informs and does not advise.** Tax reports, projections and gain/loss figures
    are worksheets for the user or their preparer. They are not tax, legal or investment
    advice, and the screens say so where it matters (S8.18).
17. **Receipts are read on the server with RapidOCR**: open source, CPU
    only, models shipped with the app, run as a sandboxed background job. Results are
    suggestions the user confirms (S9.8).
18. **What a link brings in is kept apart and encrypted**. Each link's shared data lives in its own **linked copy**: a SQLCipher
    database plus one encrypted file per receipt, in a folder of its own, never in the main
    database. It opens with the copy's own **access key**, 12 generated words that the
    receiving household keeps in its password manager, never with the master key. The key
    protects the copy at rest; who sees what is decided by the owner's shares. The copy
    keeps syncing while it is locked, and its key is released after an hour unused (S11.9).
19. **Beyond investments**: MoneyKata also covers **529 plans** (S1.8),
    **mortgages and other loans** with payoff and overpayment projections (S1.9, S6.10),
    **physical assets** such as precious metals, collectables, property and vehicles, with
    notes, purchase dates and cost basis (S1.10), **gifts** to the people in a user's life
    for their birthdays, anniversaries and holidays (S7.7, S7.8), and **charitable giving**
    against a target set as a percentage of income (S7.9).
20. **Schema conventions**: tables are declared with SQLAlchemy Core,
    with no logic beside them, and mapped onto plain dataclasses (S14.1). Table names are
    singular and capitalized, field names camelCase, and primary keys a short prefix plus a
    Crockford-encoded UUIDv7, such as `User_01k7ab4vstfggspkjt3my8wzr2`.
    [`schema.md`](schema.md) holds the conventions and the list of prefixes.
21. **Taxes are kept in tax books**: one per user, or married couple,
    and year. A tax book holds the documents received and one **filing** per return
    (federal, state, local), each with the forms as filed, the tax authority's letters and
    any amendment. Another user can be given write access to help prepare it (S8.14).
    MoneyKata still prepares worksheets only and never files.
22. **Owners choose people on other servers**. Linked servers exchange
    their lists of active users, so an owner shares any of the seven shareable kinds (account,
    portfolio, budget, person, giving plan, tax book, projection) with named people on another server,
    as they do with people on their own (S10.3). What a household shares is shown in a
    **window of its own**, never mixed with this household's data (S12.10). This suits
    household servers; a server for more than a household would need users to opt in to
    being listed ([out of scope](out-of-scope.md)).
23. **US dollars only.** Every account, price, total and report is in USD. There are no
    foreign accounts and no currency conversion (S4.8, [out of scope](out-of-scope.md)).
24. **Records are soft-deleted.** Deleting marks a record deleted, with when and by whom, and
    a view per table works out whether it is deleted through what it belongs to. The few
    exceptions are listed in [`schema.md`](schema.md) (S14.1.5).
25. **Alerts** tell people when something needs them, above all admins when a source has
    failed for more than 48 hours. They show as a live count on the **Alerts** screen, and
    each user chooses to be emailed each one, a daily summary, or nothing (S12.11).
26. **Account data comes from files the user brings.** Bank, card, brokerage and exchange
    accounts are kept current from files: OFX/QFX and CSV downloads, PDF statements, and
    photos of statements read on the server. There is no bank-aggregation service (S1.3,
    [rejected ideas](rejected-ideas.md)). **Bitcoin** is the one chain watched, through a public explorer or the household's
    own node; other coins and exchanges' APIs come later (S1.5, S1.6).

# R2. Terminology

1. **Institution:** a bank, broker, exchange, plan administrator or blockchain that holds the
   money. It is a label on an account, not an entity with credentials.
2. **Account:** one place money is held, owned by one user: a checking account, a brokerage
   account, a Roth IRA, a Coinbase account, a Bitcoin wallet. Every account has an **account
   type** (S1.1) that decides its fields, tax treatment and screens.
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
   its realized and unrealized gain or loss. Options are positions (S3).
8. **Portfolio:** a named set of accounts, or of a part of them (S5), owned by one user and
   charted as one. *All my accounts* is everyone's implicit first portfolio.
9. **Share:** a grant of one account or portfolio to a user, a group or a linked server, at a
   **level**: `read` or `write` (S10). A share to a linked server is always `read`.
10. **Linked server (peer):** another MoneyKata server this one has a **link** with (S11).
    What a link brings in is kept in that link's **linked copy**, encrypted under its own
    **access key**: 12 generated words that the receiving household keeps. The copy is
    **locked** until someone it shares with enters the words, and locks again after an hour
    unused. It is shown in its own **linked household** window (S11.9, S12.10).
11. **Price source:** an integration (a `TickerSource`) that supplies daily prices for one
    or more instrument classes (S4).
12. **Projection:** how money will grow toward a goal (retirement, education or a savings
    target), from contributions, returns and withdrawals over time. An **active** projection
    is the plan being followed, tracked against its baseline (S6).
13. **Budget:** a period's planned amounts per category, compared with the actual
    transactions (S7).
14. **Receipt:** an uploaded file (PDF, JPEG, PNG, HEIC, WebP) with a date, an amount and
    links to what it supports (S9).
15. **Tax book:** the tax records of one user, or of a married couple filing jointly, for one
    **tax year** (a calendar year): the tax documents they received (W-2s, 1099s), and a
    **filing** per return (federal, state or local) with the forms as filed and what the tax
    authority sent back (S8.14–S8.17). The Taxes screen shows one tax book at a time.
16. **Loan:** a liability account with terms (principal, rate, term, payment) from which
    MoneyKata computes an **amortization schedule**. A **mortgage** is a loan secured by a
    property. An **overpayment** is principal paid beyond the schedule (S1.9).
17. **Physical asset:** a thing of value that is not a security: precious metals,
    collectables, property, a vehicle. A physical-asset account holds **items**, each with
    its own purchase date, cost basis, valuations and notes (S1.10).
18. **Person:** someone in a user's life who is not necessarily a user of the server: a
    child, a parent, a friend. A person has dates (**occasions**) such as a birthday or an
    anniversary, and can be a 529 plan's beneficiary (S7.7).
19. **Gift:** something given to (or received from) a person for an occasion, from idea to
    given, with its cost (S7.8). **Giving** means charitable donations, tracked against a
    **giving target** (S7.9).
20. **Words not used:** *Wallet* for anything but a self-custody crypto wallet. *Asset* on
    its own for a security: the UI says holding or instrument, and keeps *asset* for
    *physical asset* (term 17). *Trade* as an entity: a trade is a pair of
    transactions on a position.

# R3. Design principles

1. **One server, on the household's own LAN.** All data stays on hardware its users control.
   The only outbound calls are to price sources, the bitcoin explorer or node, and linked
   servers that a user or admin set up, and each is visible in Settings (S16).
2. **The ledger is the truth.** Holdings, balances, positions, gains and charts are derived
   from transactions and lots. A **balance snapshot** may stand in for history where none is
   available, such as an opening balance or a 401(k) statement, and it is marked as such.
3. **Exact arithmetic.** Decimals everywhere, with rounding only at display or where the tax
   rules say to round (S14.3).
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
   from it, and a check fails on drift (S17.5).
