# MoneyKata's API

Two HTTP interfaces, both on the server's own address. The requirements set their rules (S13.8
the conventions, S10.9 agents); this page says how to use them.

| Path        | Who calls it                            | Signs in with                       |
|-------------|-----------------------------------------|-------------------------------------|
| `/ui/api`   | the browser app                         | the session cookie (S13.7.1)         |
| `/mcp`      | an AI assistant, read only (S10.9)      | an access token made in Profile      |

`/link` is the protocol between linked servers: `docs/link-protocol.md`.

## 1. `/ui/api`

The browser app's API. It changes with the app and carries no version of its own (S13.8.9).

- **Its contract** is `web/ui/api/openapi.json`, generated from the routes, with the browser's
  JSDoc types in `web/ui/api/types.js`. `web/check` fails when either differs from what the
  routes give. The server doesn't serve the document: read it from the repository.
- **Numbers are exact** (S13.8.2). Money, quantities, prices and ratios are JSON numbers
  written with their own digits and always a decimal point: `1234.50`, `10.0`, `0.0345`. Read
  them without a float: in Python, `json.loads(text, parse_float=Decimal)`; in the browser, the
  app's `parseJson` (`web/ui/app/dec.js`), which gives each one as a `Dec`. A whole number
  with no decimal point (a count, a year, a version) is an integer. Requests send amounts the
  same way; a decimal string, as a form field gives it, is accepted too. A float that has lost
  digits can't be told from one that hasn't, so send the text the person typed.
- **The rest of the conventions** (resources, errors as `application/problem+json`, status
  codes, paging, `If-Match` versions, jobs for long work, `Idempotency-Key`, visibility) are in
  S13.8.

## 2. `/mcp`

The Model Context Protocol over HTTP: JSON-RPC 2.0 in one `POST /mcp` per call, with
`Authorization: Bearer <token>`. A token is made in **Profile › Access tokens**, read only by
design: an assistant can read what its user can see and never change anything. A token for
**chosen items** reads only the accounts and portfolios it names, and is refused the tools
about the whole household (marked *household* below). Each call is limited to 60 a minute per
token and recorded in Activity under the token's name. Answers carry exact numbers as above.

| Tool                   | Reads                                                        | Arguments |
|------------------------|--------------------------------------------------------------|-----------|
| `list_accounts`        | every account the token reads: type, balance, 30-day change  | none |
| `get_account_holdings` | what an investing account holds: quantity, value, cost, gain | `account_id` |
| `list_transactions`    | transactions, newest first, at most 500                      | `account_id`, `from`, `to` (dates), `payee`, `limit` |
| `list_positions`       | open and closed positions, realized and unrealized gains     | `kind`: `all`, `stocks`, `options` or `crypto` |
| `list_portfolios`      | the portfolios the token reads, with accounts and value      | none |
| `get_portfolio`        | one portfolio: value, holdings by instrument, returns        | `portfolio_id` |
| `list_budgets`         | the budgets the user can see (*household*)                    | none |
| `get_budget_month`     | a budget's month: planned and spent by category (*household*) | `budget_id`, `month` (`YYYY-MM`) |
| `list_upcoming_gifts`  | birthdays and holidays coming up, with gift plans (*household*) | none |
| `get_giving`           | a year's giving by organisation, and its plan (*household*)  | `year` |
| `list_tax_books`       | the tax books the user can see (*household*)                  | none |
| `get_tax_panels`       | a tax book's panels and what is missing (*household*)         | `book_id` |

`tools/list` gives each tool's full argument schema. A test fails when a tool is missing from
this table.
