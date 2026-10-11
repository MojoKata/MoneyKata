# MoneyKata: database schema conventions

Status: decided 2026-10-11. These conventions apply to the main database and to every linked
copy (requirements §14.9, §17.1). The tables are declared with SQLAlchemy Core in
`web/server/src/moneykata/store/tables/` (requirements §20.1).

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
- **IDs reveal when a row was created.** File names and anything else visible on disk,
  such as receipt files and a linked copy's files (requirements §14.9), use separate random
  names and never an ID.

```
UUIDv7 (hex):   0199d4b2-6f3a-7c21-9b4e-5a1d3c8e7f02
Crockford:      01k7ab4vstfggspkjt3my8wzr2
Transaction ID: Txn_01k7ab4vstfggspkjt3my8wzr2
```

## 3. Prefixes

This first list covers the entities named in requirements §2 (Terminology). It grows as
tables are designed. Tables for many-to-many relationships have no prefix (§1.2), so they
are not listed.

| Prefix | Table       | Description                                                                       |
|--------|-------------|-----------------------------------------------------------------------------------|
| Acct   | Account     | One place money is held, owned by one user, with an account type.                 |
| AsItm  | AssetItem   | One item in a physical-asset account, with its cost basis and valuations.         |
| Bdgt   | Budget      | A period's planned amounts per category.                                          |
| Cat    | Category    | A budget category given to bank transactions.                                     |
| Dnatn  | Donation    | One charitable gift to an organisation, or a donor-advised fund grant.            |
| Filng  | Filing      | One return in a tax book (federal, state or local), with its progress and result. |
| Gift   | Gift        | A gift to or from a person for an occasion, from idea to given.                   |
| Group  | Group       | A named set of users that shares are granted to.                                  |
| Hold   | Holding     | What an account holds of one instrument at a point in time.                       |
| Instr  | Instrument  | A thing with a price: a stock, fund, coin, option contract or currency.           |
| Link   | Link        | A link with another MoneyKata server.                                             |
| Lot    | Lot         | One acquisition of an instrument, and what remains open.                          |
| Occsn  | Occasion    | A dated occasion for a person: a birthday, an anniversary, a holiday.             |
| Persn  | Person      | Someone in a user's life who need not be a user of the server.                    |
| Portf  | Portfolio   | A named set of accounts, or parts of them, charted as one.                        |
| Postn  | Position    | An instrument held in an account, followed from open to closed.                   |
| Prjct  | Projection  | A saved scenario of contributions, returns and withdrawals.                       |
| Rcpt   | Receipt     | An uploaded file with a date, an amount and links to what it supports.            |
| Share  | Share       | A grant of an account or portfolio to a user, group or linked server.             |
| TaxBk  | TaxBook     | One user's, or a married couple's, tax records for one tax year.                  |
| TxDoc  | TaxDocument | A tax document received (W-2, 1099) or filed (a return, a notice), with its file. |
| Txn    | Transaction | One dated movement in an account.                                                 |
| User   | User        | A person who signs in to this server.                                             |

## 4. Checks

A test fails when:

1. a table or field name breaks §1;
2. a table with an `id` has no row in §3, a row in §3 names no table, or §3 is not sorted
   by prefix;
3. a table with an `id` lacks the `WITHOUT ROWID` option or the ID's `CHECK` constraint.
