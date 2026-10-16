# S16. Settings (admins)

One screen with a section list on the left, **General first** and selected when Settings
opens. Each section has its own help guide. In the order below, except Storage (17), which
follows Backups, and Connector (18), which follows Linked servers:

1. **General**: server name (shown to linked servers), the **household name and avatar** (an
   image, or initials; shown at the top of the sidebar here, and sent to linked servers,
   which always show them as set here, S12.10), public URL (links in emails are built from
   it, never from the request), and the server's time zone, read from the host (S14.9).
2. **Email (SMTP)**: host, port, security (STARTTLS, TLS or none), username, password (a
   secret), from address, and **Send a test email**, which sends to the admin at once and
   says what failed. Until a host is set, emails are written to the mail folder in the data
   directory. With one, they go out in the background: an email that can't be sent stays
   queued and is tried again every five minutes, one the server refuses outright is set
   aside, and the section shows the queue and the last error.
3. **Sign-in and sessions**: idle and absolute session lifetimes, lockout after failed
   sign-ins.
4. **Sign-up**: on or off (it needs SMTP), optionally limited to email domains.
5. **Passwords**: the minimum length (12 by default, at least 8).
6. **Prices** (S4.2.3): the enabled sources with their classes, keys, order, last run and
   error; **Add a source**; and the time of the daily refresh (6:00 PM Eastern by default).
7. **Bitcoin** (S1.6): the explorer or node for self-custody wallets: a public Esplora
   (mempool.space by default, or Blockstream) or the household's own node (its own mempool or
   Esplora by its address; an Electrum server by host, port and TLS; Bitcoin Core by host,
   port, RPC user and password), with when the wallets were last read and a **Test** button.
8. **Imports** (S1.3): the file types and size accepted for statement import, and whether
   statements are read on the server (in the receipt reader's worker, S9.8).
9. **Linked servers** (S11.7): the links, and each linked copy's state: changes waiting, its
   access key (*Create the access key*, made when and by whom), locked or unlocked (by whom,
   and when it will lock), *Lock now* and *Reset copy*, and **Release linked keys after**
   (one hour unused by default).
10. **Receipts**: the size limit and allowed types; **Read receipts** on or off, jobs at a
    time, the reading queue, and **Re-read all receipts** (S9.8.7).
11. **Tax tables**: per year, shipped and correctable: contribution limits and thresholds,
    the annual gift exclusion, the 529-to-Roth lifetime limit, the QCD limit, the
    collectables rate, the unearned income above which Form 8615 applies (S8.14.5.3), the
    shipped college-cost averages (S6.2.2), the bitcoin models' published figures (S6.3.1),
    and the metal per share of SLV, PPLT and PALL (S4.3).
    A corrected figure is marked, with the shipped value beside it; setting it back to the
    shipped value removes the correction. A year after the latest shipped uses the latest.
    The college-cost averages and the metal per share arrive with the features that use
    them (529s, physical assets).
12. **Backups**: the time of day and the copies kept; the backup directory is set on the host.
13. **Key storage** (S15): read-only. The master key's fingerprint and age, who confirmed
    its recovery phrase and when, rotation progress and the date the previous key can go
    (counting the backup directory's own copies only, and saying so: copies kept elsewhere
    are the admin's to count, S15.7.1.4), the progress of a re-encryption, and anything that
    cannot be opened. Buttons: **Test** and **Re-encrypt**, with what re-encryption is for
    and that it closes no copy made before it (S15.7.2). The master key itself is only ever
    changed on the host.
14. **Network**: the address ranges allowed to reach each path, one list per line, empty for
    any: **the app** (`/ui`, and `/mcp` with it: an agent sits where a person's browser does,
    and its token is already the user's); **linked servers** (`/link`); and **the connector**
    (`/connector`, S18), the LAN and the overlay by default, so a connector on a laptop away
    from home (S18.1) needs an admin to widen it. `/healthz` and `/demo` answer any address.
15. **TLS** (in `tls` mode): the listener's certificate and key.
16. **Alerts** (S12.11): how long a source may fail before it raises an alert (48 hours
    by default), and the time of the daily summary email (07:00 by default, in each user's
    time zone).
17. **Storage** (S14.10): the size of the database and of the receipts directory, files
    expired against the rest, what expires each coming year by category, **Keep statements
    for** (years, empty for ever), each category's **Keep receipts for**, and **Prune**.
18. **Connector** (S18): pairing with the MoneyKata Connector (**Pair**, the connector's
    fingerprint, **Unpair**), whether it is locked, its last report, and every Connection's
    state, owner and accounts, never their credentials.
