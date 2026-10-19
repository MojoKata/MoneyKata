# Check a brokerage statement

A brokerage or plan statement's PDF, read from its text layer: its summary, its positions on the
last day and its cash activity, checked here before anything is saved. A photo or scan isn't read,
since its tables don't survive OCR reliably: keep it on the account instead.

## Summary {#summary}

The starting and ending value, deposits, withdrawals, income and the change in value. The ending
value becomes a balance anchor on the last day, checked on the Reconcile tab against what the
account was worth that day, cash and holdings at that day's prices.

## Positions {#positions}

Each holding the statement shows, against what MoolaKata holds that day. A difference is shown,
and pointed at the statement's own trade lines when they account for it (a reinvestment or a buy
not entered yet). The statement's cost basis is kept beside the lots' and never written over them.
For an account kept by snapshots (kept from statements only, with no trades of its own), the
positions become its holdings on that date. The cash or sweep line is checked against the account's
cash, and becomes a cash anchor.

## Cash activity {#cash-activity}

Deposits, withdrawals, dividends, interest and fees, each kept as a transaction when ticked. Lines
already in the account start left out, and every line does when the account's files already carry
its activity. When the lines read don't add up to the summary's figures, a line may not have been
read: check them.

Trades, options activity, corporate actions and margin lines aren't read. A trade opens the trade
dialog with its figures filled in; the others are entered by hand.
