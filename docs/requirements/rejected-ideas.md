# Rejected ideas

Ideas that were weighed and turned down, kept so they are not raised again without a new
reason.

1. **A separate keys process** that alone reads the master key and wraps and unwraps keys over
   a Unix socket. A compromised web process could then not copy the key, but it costs a
   second account and a socket, and the web process can already read everything the key
   protects while it runs. The server's own account reads the key file (S15.4).
2. **External key services** (HashiCorp Vault, cloud KMSs, HSMs, TPM sealing): another
   service to run, back up and secure, for little gain over a key file with offline backups
   (S15.2).
3. **Leaving the financial data unencrypted** and relying on disk encryption and encrypted
   backups. Backups leave the house, so the database and receipts are encrypted by MoneyKata
   (S15.1).
4. **The master key written as base32** on a recovery sheet. Twelve BIP39 words are easier
   to write down, read back and type, and catch typos better (S15.6.1).
5. **A personal access key per user for linked copies**, with the copy key sealed to each
   user (by a passphrase of their own, or by their password). The owner's shares already
   decide who sees what, so the key only has to protect the copy at rest. One key per copy,
   unlocked for the server, is simpler and recovers more easily (S11.9.3).
6. **The receiving admin choosing who sees each linked share.** Servers exchange their user
   lists, so the owner names the people (S11.3).
7. **Linked accounts shown among this household's own**, as locked rows, in totals or inside
   local portfolios. Another household's data is a world of its own and opens in its own
   window (S12.10).
8. **SQLModel** for the tables. It merges the table, the API model and the entity into one
   class. Tables are declared with SQLAlchemy Core and mapped onto plain dataclasses, so the
   schema carries no logic (S14.1).
9. **A portfolio showing an account its viewer can't see** as one line with its value. It
   still discloses a figure the owner didn't share; viewers see only what is shared with
   them, and the Share dialog offers to share the rest (S5.1).
10. **Write access for agents.** An agent reads through a token and can never change
    anything, whatever shares its user holds (S10.9).
11. **An RPM** with its own Python, beside or in place of the Docker image. A home server is
    far more often a NAS, a Raspberry Pi or a container host than a RHEL machine (S17.8).
12. **Barchart** for prices. Its website's terms forbid robots, data mining and applications
    built on it without written consent, and its API (OnDemand) is a paid commercial
    product (S4.1).
13. **Stooq** as the no-key source for daily prices and metals spot. Since 2026 its downloads
    need a key obtained through a captcha, with a daily quota, which a server can't keep up
    (S4.3).
14. **Yahoo Finance** (unofficial). It has no API terms and breaks without notice.
15. **Bank aggregation** (SimpleFIN Bridge and the like). It costs each user a subscription
    and gives a third party standing read access to their accounts. Statements and exports
    the user downloads cover the same ground (S1.3).
16. **Pruning records** from the database, leaving yearly or monthly summaries in their
    place. A household's rows grow by about 10 MB a year, while its receipt and statement
    files grow 50 to 100 times faster; removing rows saves little, loses history that
    can't be brought back once backups age out, and makes every report add summaries to
    what survived. Only files are pruned, by their retention (S14.10).
17. **A key per backup**, or any way to close a copy already made, after a master-key leak:
    re-wrapping each backup's keyring under a key the leaked phrase does not open. Whoever
    holds the leaked phrase and a copy of the backup as it was already has its data key; a
    later re-wrap changes only the copy MoneyKata still holds, not theirs. A copy opens with
    the keys of its day for as long as it exists, so the answer to a leak is to delete the
    copies, not to re-key them (S15.7.3, S15.8).
