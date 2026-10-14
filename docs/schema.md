# MoneyKata: database schema conventions

These conventions apply to the main database and to every linked copy (requirements S11.9,
S14.1). The tables are declared with SQLAlchemy Core in
`web/server/src/moneykata/store/tables/` (requirements S17.1).

## 1. Naming

1. **Tables** have a capitalized, singular name: `User`, not `Users`.
2. **Tables for many-to-many relationships** have plural names: `UserGroups`,
   `TaxBookFilers`.
   Their primary key is the pair of foreign keys (`userId`, `groupId`). They have no `id`
   column and no prefix.
3. **Field names** are camelCase and start with a lowercase letter.
   1. Acronyms of 3 or more characters are written as words.
   2. For example, `encodeHtml` or `htmlEncode`, not `encodeHTML` or `HTMLEncode`.
4. **Primary keys** are named `id`. A foreign key to a table ends with `Id`: `userId`.
   1. A primary key is the table's prefix, an underscore, and a Crockford-encoded UUIDv7
      (§2): `User_01k7ab4vstfggspkjt3my8wzr2`.
   2. The alphabet is in ascending byte order, so sorting the strings gives the same order
      as sorting the UUIDs. The first 10 characters (`01k7ab4vst`) are the 48-bit
      millisecond timestamp, since 10 × 5 = 50 bits covers the 48-bit time plus the 2
      padding bits.
5. **Prefixes** are tracked in the table in §3, sorted by prefix in byte order (`A`–`Z` before
   `a`–`z`). Each row gives:
   1. the prefix (slug),
   2. the table's name,
   3. a description of the table.

The same names are used in Python and in the API's JSON. A table's columns, the attributes
of its entity dataclass and the fields the browser receives all have the same spelling, so
there's no layer that translates names.

## 2. Primary keys

- **The prefix** is at most 5 characters, starts with a capital letter, and is unique
  across all tables. With the underscore, it takes up to 6 characters.
- **The UUIDv7** is encoded as one 128-bit number in base 32, most significant digit first,
  in exactly 26 lowercase characters from the alphabet `0123456789abcdefghjkmnpqrstvwxyz`.
  The letters `i`, `l`, `o` and `u` are not used.
  - The first character is always `0`–`7`, because 26 × 5 = 130 bits.
  - The decoder rejects uppercase letters and the letters left out of the alphabet, so each
    ID has exactly one spelling.
- **Column:** `id TEXT PRIMARY KEY`. Each table with an `id` is a `WITHOUT ROWID` table and
  has a `CHECK` constraint on the ID's form:
  ```sql
  CHECK (id GLOB 'User_*' AND length(id) = 31)
  ```
  The length is the prefix's length + 1 + 26.
- **Record fields.** Each table with an `id` also has `version` (an integer that changes with
  every save, which the API's `If-Match` compares, requirements S13.8.6), `createdAt` and
  `updatedAt`.
- **IDs reveal when a row was created.** File names and anything else visible on disk,
  such as receipt files and a linked copy's files (requirements S11.9), use separate random
  names and never an ID.

```
UUIDv7 (hex):   0199d4b2-6f3a-7c21-9b4e-5a1d3c8e7f02
Crockford:      01k7ab4vstfggspkjt3my8wzr2
Transaction ID: Txn_01k7ab4vstfggspkjt3my8wzr2
```

## 3. Prefixes

Tables for many-to-many relationships have no prefix (§1.2), so they are not listed. Each
list is sorted by prefix, and a prefix is unique across both.

### 3.1 Tables

The prefixes of the tables that exist.

| Prefix | Table            | Description                                                                                  |
|--------|------------------|----------------------------------------------------------------------------------------------|
| Acct   | Account          | One place money is held, owned by one user, with an account type.                            |
| Actv   | Activity         | A change worth showing: who made it and what it is about, never an amount.                   |
| Alert  | Alert            | Something that needs a user's attention, one per cause, open until the cause clears.         |
| Anchr  | Anchor           | A balance the institution reported on a date, that the account's balance is checked against. |
| Asmpt  | AssumptionSet    | A user's expected returns, volatility and inflation for projections.                         |
| BdgLn  | BudgetLine       | One category's planned amount in a budget, from a month on, monthly or yearly.               |
| Bdgt   | Budget           | A user's plan per category over chosen accounts; shared with a group for a household.        |
| Cat    | Category         | A budget category given to bank transactions.                                                |
| Cntrb  | Contribution     | Who a deposit into a 529 came from, and whether it is a five-year election.                  |
| Dnatn  | Donation         | One charitable gift to an organisation, into a donor-advised fund, or a grant from one.      |
| EdPln  | EducationPlan    | A 529 account's plan: its state, name, beneficiary and opening date.                         |
| EstPy  | EstimatedPayment | A filing's estimated tax payment for a quarter, matched to its transaction.                  |
| Filng  | Filing           | One return in a tax book (federal, state or local), with its progress and result.            |
| Gift   | Gift             | A gift to or from a person for an occasion, from idea to given.                              |
| Group  | Group            | A named set of users that shares are granted to.                                             |
| GvPln  | GivingPlan       | A user's giving target for a year: a percentage of income, or an amount.                     |
| Hold   | Holding          | What an account holds of one instrument at a point in time.                                  |
| Imprt  | Import           | One file imported into an account, with the dates it covers.                                 |
| Imprv  | Improvement      | An improvement to a property, added to its cost basis.                                       |
| Instr  | Instrument       | A thing with a price: a stock, fund, coin, option contract or currency.                      |
| Item   | Item             | A physical asset: metals, a collectable, a property or a vehicle, with how it is valued.     |
| Loan   | Loan             | A loan account's terms: principal, rate, term, escrow, PMI, resets and recasts.              |
| Lot    | Lot              | One acquisition of an instrument, and what remains open.                                     |
| Lyout  | StatementLayout  | What statement import learned of an institution's layout: section signs, lines to skip.      |
| Map    | ImportMapping    | A saved column mapping for one institution's CSV files.                                      |
| Occsn  | Occasion         | A dated occasion for a person: an anniversary, a holiday, a custom date.                     |
| Orgzn  | Organisation     | An organisation given to: its EIN, whether gifts to it are deductible, causes, pledges.      |
| Persn  | Person           | Someone in a user's life who need not be a user of the server.                               |
| Portf  | Portfolio        | A named set of accounts, or parts of them, charted as one.                                   |
| Prjct  | Projection       | How money will grow toward a goal; an active one is tracked against its baseline.            |
| Pyoff  | PayoffPlan       | A saved overpayment plan for a loan; one may be the plan being followed.                     |
| QExpn  | QualifiedExpense | A qualified education expense a 529's withdrawals are matched with.                          |
| Rcpt   | Receipt          | An uploaded file, encrypted on disk, with a date, an amount and what it is attached to.      |
| Recon  | Reconciliation   | A statement's closing date and balance, ticked off against the transactions.                 |
| Secr   | Secret           | A secret sealed on its own: an API key, a password or a private key.                         |
| Sgnup  | SignupRequest    | A person's request for an account, from confirming the email to an admin's decision.         |
| Share  | Share            | A grant of an account or portfolio to a user, group or linked server.                        |
| Split  | Split            | A part of a transaction's amount given its own category.                                     |
| Src    | PriceSource      | A source of daily prices: its name, whether it is on, and its order per class.               |
| TaxBk  | TaxBook          | One user's, or a married couple's, tax records for one tax year.                             |
| TaxFg  | TaxFigure        | An admin's correction of a shipped tax-table figure for one year.                            |
| TxDoc  | TaxDocument      | A tax document received (W-2, 1099) or filed (a return, a notice), with its file.            |
| Txn    | Transaction      | One dated movement in an account.                                                            |
| User   | User             | A person who signs in here, or a user of a linked server (with `linkId`).                    |
| Valtn  | ItemValuation    | A dated value of an item, with its source.                                                   |

### 3.2 Reserved

The prefixes of the entities named in requirements R2 (Terminology) whose tables are not
designed yet. A row moves to §3.1 when its table is.

| Prefix | Table         | Description                                                                       |
|--------|---------------|-----------------------------------------------------------------------------------|
| Link   | Link          | A link with another MoneyKata server.                                             |
| Postn  | Position      | An instrument held in an account, followed from open to closed.                   |
| Token  | AccessToken   | A user's read-only token for the MCP endpoint, stored as a hash.                  |

## 4. Soft deletes

Records are never removed from the database: they are marked deleted. The exceptions are in
§4.4.

1. **Fields.** Every table, many-to-many tables included, has:

   | Field         | Type      | Meaning                                                  |
   |---------------|-----------|----------------------------------------------------------|
   | `deleted`     | boolean   | the record itself was deleted                            |
   | `deletedAt`   | timestamp | when; null while `deleted` is false                      |
   | `deletedById` | `User` FK | who; null when the server deleted it (a sync, a job)     |

   A `CHECK` keeps them consistent: `deleted = (deletedAt IS NOT NULL)`, and `deletedById` is
   null while `deleted` is false. Restoring a record clears all three. Re-adding a row that
   a many-to-many table already holds as deleted restores it.
2. **Effective deletion.** A record is also deleted when something it belongs to is: a
   transaction when its account is, a gift when its person is. *Belongs to* is a foreign key
   declared `ondelete="CASCADE"` to a soft-deletable table. Each table has a view, named
   `<Table>Effective` (`TransactionEffective`), with every column of the table plus:
   1. `effectiveDeleted`: the record's own `deleted`, or the `effectiveDeleted` of any record
      it belongs to;
   2. `effectiveDeletedAt`: the earliest `deletedAt` along that chain.

   The views are generated from the table declarations, chaining each parent's view, so a
   new cascading foreign key changes the view with it. Code reads through the views and
   leaves out effectively deleted records unless it asks for them.
3. **Uniqueness** ignores deleted records: a unique index is partial, `WHERE NOT deleted`, so
   a deleted name or username can be used again.
4. **Exceptions**, removed outright:
   1. **sessions and one-time tokens** (invitation, sign-up confirmation, reset, email
      change, a sign-in waiting for its two-step code), when used or expired, and two-step
      recovery codes when used or replaced;
   2. **a secret's old ciphertext** when the secret is replaced or removed, so an old API key
      or token can't be recovered from the database or a later backup;
   3. **linked copies**: another household's data, removed with the share or link it came
      by, at **Reset copy**, and an inbox change once it is applied (requirements S11.9);
   4. **work queues and counters**: receipt-reading jobs, sign-in and access-key attempt
      counters, the background tasks' last runs, and the live stream's state;
   5. **caches**, rebuilt from the records: thumbnails, and computed series kept for speed.

   Activity entries and alerts are never deleted at all: Activity is kept as it was
   written, and alerts are resolved, then age out of the list (requirements S12.11).

## 5. Checks

A test fails when:

1. a table or field name breaks §1;
2. a table with an `id` has no row in §3.1, a row in §3.1 names no table, a prefix is listed
   twice, or a list in §3 is not sorted by prefix;
3. a table with an `id` lacks the `WITHOUT ROWID` option or the ID's `CHECK` constraint.
4. a table outside the exceptions of §4.4 lacks the fields of §4.1 or their `CHECK`, or its
   `<Table>Effective` view is missing or does not match its cascading foreign keys.
