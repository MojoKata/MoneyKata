# S12. Web UI

1. **Frame**: drawn once around every signed-in screen, from one list of navigation entries;
   no screen draws or changes it.
   1. A **sidebar** pinned to the viewport: the household's avatar and name with the version
      (and a red **DEV** pill in dev mode), the navigation with count badges, and at its
      foot the signed-in user's
      tile with the **theme** button (crescent moon for dark, lightbulb for light, palette
      for the system's; a click moves to the next). A round button on its edge collapses it
      to icons and opens it again; the browser remembers which.
   2. The **help pane** on the right (S12.7), and a **toast** area for confirmations.
   3. Shared components: one popup menu (closes on choosing, Escape, or a click or focus
      outside), dialogs that trap focus and return it, styled tooltips that also show on
      keyboard focus and reach screen readers, and a **pager** for long lists (Transactions,
      Activity): a page size of 100, 500 or 1000 kept per browser, the rows shown out of the
      list's total ("1–500 of 2,624") with a jump to its pages (S13.8.5), and rows that arrive
      while reading counted on an orange **+N new** pill instead of shifting the page. Every
      password field (a password, an API key, the SMTP or node password) carries an **eye**
      button at its right end that shows what was typed and hides it again (the eye struck
      through while shown), labelled for screen readers.
   4. An orange **update** pill under the brand when the server was upgraded since the page
      loaded; a click reloads.
2. **Navigation** (in this order):
   1. **Dashboard**: net worth and its change (day, month, year), the net-worth chart,
      allocation, accounts by group with balances, this month's budget, upcoming recurring
      transactions, occasions inside their reminder time (S7.7.3), giving against its
      target, the **Plans** card of active projections (S6.8), and stale prices, stale
      valuations, or sources and imports that need attention;
   2. **Accounts**: every account the user owns or holds a share of, grouped (Banking,
      Investing, Retirement, Education, Crypto, Giving, Liabilities, Physical assets), each with its type icon,
      institution, balance, change, when it was last updated, and sharing marks. **New account** offers a
      type picker, then the account form. An **account page** has the tabs *Overview*
      (balance chart), *Holdings* (investing only), *Transactions*, *Positions* (investing
      only), *Receipts*, *Reconcile* (banking, card, brokerage and loan accounts, S1.11),
      *Sharing* and *Settings* (how it is kept current, lot method, import mappings).
      Some types add tabs: a loan *Schedule* and *Payoff* (S1.9, S6.10); a 529
      *Contributions*, *Withdrawals* and *Goal* (S1.8); a physical-asset account *Items*
      (S1.10);
   3. **Transactions**: every account's transactions together, filtered by account, category,
      date, amount, payee and tag, with bulk categorise, split, attach receipt, and **Import**;
   4. **Portfolios**: the user's portfolios and those shared with them; a portfolio page with
      the charts of S5.2, its holdings, and its *Projections*;
   5. **Positions**: open and closed positions across accounts, with stocks, options and
      crypto as filters, and P/L per S3.9. **Record trade** opens the trade dialog, which has
      an option leg builder;
   6. **Budgets**: the month view, cash flow, trends, recurring transactions and rules;
   7. **Projections**: active projections first, with their tracking, then the scenarios;
      each with its inputs and the fan chart (S6);
   8. **Gifts**: *Upcoming* occasions, *People*, *Gifts* (ideas to given, and received), and
      *Spending* by person, occasion and year (S7.7, S7.8);
   9. **Giving**: the year's target and progress, donations, organisations and the DAF
      (S7.9);
   10. **Taxes**: the tax-book picker (year and filers), **New tax book** and **Share**, then
       the panels of S8, with *Filings* and *Documents* (received and filed, S8.14–S8.17);
   11. **Receipts**: the inbox and every receipt, with a grid or list view and upload;
   12. **Watchlist** *(small)*: instruments the user follows without holding them;
   13. **Activity**: the changes of S10.8, newest first, filtered by account and person;
   14. **Users and Groups**, **Settings** (admins);
   15. **Alerts**: what needs the user's attention, with a live count on its badge (S12.11);
   16. the user tile opens **Profile** (name, email, avatar, password, two-step, alert
       emails, time zone (S14.9), assumptions for projections (S6.3), access tokens, birth
       year, spouse for
       wash sales) and **Sign out**.
3. **Privacy mode**: a button in the header (an eye) blurs every amount on the page until
   clicked again, for using the app with someone looking over your shoulder. The browser
   remembers it.
4. **Numbers**: tabular figures, right-aligned, with the dollar sign. Gains are green and
   losses red, *and* signed with + or −, so colour is never the only cue. Large values are
   abbreviated in charts only ($1.2M), never in tables.
5. **Every value derived from a price** shows its age on hover, and the header shows the last
   price refresh with a dot that turns amber when prices are stale (S4.7).
6. **Live updates**: the frame keeps one Server-Sent Events stream open (`GET
   /ui/api/events`). It carries fingerprints and counts, never data: prices refreshed, an
   import finished, a statement read, a share received or removed, a linked pull done, a
   background task finished (a backup, a re-encryption), a sign-up request (for admins), a new alert, the badges' counts (Alerts among them), and the server's version. A screen whose data changed reloads it through
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
      app and an in-page fake backend, for the screens built so far, the linked household
      window among them (recorded from a seeded peer with its copy unlocked), and `web/check`
      fails while it is out of date.

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
          source server sets them (S16.1);
       2. the sidebar tinted with **a colour each user chooses** for that household, from a
          fixed palette that reads well in dark and light themes. A new household gets the
          next unused colour. The name, avatar and a header strip always show as well, so
          colour is never the only sign;
       3. a **header strip**: *griffin-parents · read only · synced 41 min ago · unlocked by
          Alice at 14:05 · Lock now*;
       4. the screens for the kinds shared with you, **every screen and tab of each**, as
          its owner sees them but read only: Dashboard (only what is shared with you),
          Accounts, Portfolios, Positions, Transactions, Projections (with their charts),
          Budgets (with cash flow and recurring payments), Gifts, Giving (with its months and
          organisations), Taxes and Receipts. The source sends what each screen needs
          (S11.3.1). The navigation lists only the kinds you have something from. There is
          no Settings, Profile, Watchlist, import, sharing or editing;
       5. the user tile shows you, the local user, *viewing griffin-parents*.
    4. **Locked**: the window shows only the household's name and avatar and the request for
       the access key (S11.9.3). If the copy locks while the window is open, the window
       returns to that request.
    5. **Never mixed**: nothing from a linked household appears in this household's lists,
       totals, charts, search, portfolios, budgets, taxes or Activity.
11. **Alerts** tell someone that something needs them. Activity records what happened; an
    alert asks for an action.
    1. **What raises one**:
       1. **for admins**: a source that has failed for longer than the threshold in Settings
          › Alerts (48 hours by default): the bitcoin explorer or node, a price source, email
          that can't be sent, or a linked server's pulls; a backup that failed;
          a link's first share waiting for its access key (S11.9.2); and the yearly check of
          the master key's recovery phrase (S15.6.5), due a year after the phrase was last
          confirmed with `keys verify`, or after the key was made. An admin's alert about someone else's
          account names its owner and source, never the account's name or figures (S10.2);
       2. **for an account's owner**: their wallet's explorer or node failing for longer
          than the threshold, an account whose next statement or import is overdue for its
          interval (S1.11.7), naming the statement missing, and a reconciliation mismatch
          left open for 7 days (S1.11);
       3. **for each user**: an occasion entering its lead time (S7.7.3), an option
          expiring within a week, a pledge due (S7.9), an active projection falling
          behind (S6.7.5), and budget alerts when they come (S7.6).
    2. **One alert per cause.** The alerts task looks at every cause every 15 minutes, and
       at once after any other background task ends. A failing source raises one alert, not one per attempt. It
       stays **open** while the cause lasts and is **resolved** by itself when the cause
       clears (the source answers again). A user can **dismiss** an open alert for themselves.
       Resolved alerts stay listed for 90 days.
    3. **The Alerts screen** lists open alerts first, newest first, then resolved ones. Each
       shows what it is about, since when, a link to the place to fix it, and **Dismiss**.
       Opening the screen marks the user's alerts as seen.
    4. **The badge** on the Alerts entry counts the open alerts the user has not seen. A new
       alert reaches the badge through the live stream (S12.6) without a reload, with a toast.
    5. **Emails**: each user chooses in Profile how alerts reach them by email:
       1. **each alert**: one email when an alert opens (not when it repeats or resolves);
       2. **daily summary**: one email a day at the time set in Settings › Alerts (07:00 by
          default, in each user's time zone, S14.9) listing the alerts opened since the last one, and none on a day without
          any;
       3. **none**: on screen only.

       Admins start on *each alert*, other users on *daily summary*. Without SMTP set up, the
       choice is shown but nothing is sent. Alert emails name the kind and the thing it is
       about, never amounts.
12. **Exact numbers in the browser.** Every amount, quantity, price and ratio the API sends
    arrives as an exact decimal (S13.8.2), a `Dec` (`app/dec.js`): a whole number of units at a
    scale, held in a BigInt. Adding, subtracting, comparing and rounding are exact, and the
    display functions format its digits as they are. It refuses to become a float by
    accident: arithmetic or a comparison with plain numbers throws, so a mistake fails loudly.
    What is only drawn (a chart's point, a bar's width) asks for a float by name. Sent back in a
    request, it is written as an exact number.
13. **Durations** are typed in one grammar wherever a length of time is asked for (pausing a
    link, S11.7.2): one or more parts, each a whole number and a unit, `w` (weeks), `d` (days),
    `h` (hours) or `m` (minutes), largest first, each unit at most once, with or without
    spaces between them: `1d`, `90m`, `2w 3d 4h`, `2w3d`. It is read by one helper on each side
    (`app/duration.js`, `moneykata/duration.py`), which refuses anything else and says why, and
    shown back the same way, so `2w 3d 4h` reads as typed.
