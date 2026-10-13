# S10. Users, groups and sharing

1. **Users, groups and sign-in**:
   1. A user has a unique username, a display name, a unique **email address**, an optional
      avatar, and a password stored as an argon2id hash. They sign in with username or email.
      The only password rule is a minimum length that admins set (12 by default).
   2. **The default admin.** A server with no users creates `admin` with a published default
      password at start. Its first sign-in leads only to a setup step: choose a password and
      give an email address.
   3. **Invitations.** Admins never set passwords. Creating a user (name, username, email,
      groups) emails an invitation link, and the user chooses their password from it.
   4. **Sign-up**, when an admin turns it on (it needs SMTP and the public URL, and can be
      limited to email domains): a person gives their name and email, confirms the email,
      and waits on a *waiting for approval* screen until an admin approves or rejects the
      request.
      1. **Asking**: from **Sign up** on the sign-in screen, with a username and a password
         chosen then, so approval leaves nothing more to do. The answer is the same whether
         or not the address already has an account; only a new address gets a link, which
         works once, for 24 hours.
      2. **Deciding**: confirmed requests show under **Requests** in Users and Groups, with a
         count on its badge. **Approve** makes the user, in a group if one is chosen;
         **Reject** turns it down. An email tells the person either way, and Activity records
         the request and the decision. The request stays as the record of it.
   5. **Password reset** by an emailed link from *Forgot password?*. A changed email address
      takes effect only when a link sent to the new address is opened.
   6. **Two-step sign-in**, optional for everyone: a TOTP code from an authenticator app after
      the password, set up with a QR code; ten recovery codes shown once; and an admin's
      reset as the last resort.
      1. **The code**: TOTP as authenticator apps read it (RFC 6238: SHA-1, six digits,
         30-second steps), with one step either side allowed for a phone's clock, and no step
         accepted twice. Its seed is a secret (S14.4).
      2. **Turning it on**, in Profile: a QR code and the same key as text, then a code from
         the app to confirm it, and only then is it on. The ten **recovery codes** follow,
         shown once, to copy or download; only their hashes are kept. Profile shows how many
         are left, warns at three, and **New recovery codes** replaces them all.
      3. **Signing in**: a right password leads to the code, through a token that lasts
         five minutes; no session exists until the code is right. A recovery code is taken
         in place of the code, once. Wrong codes count toward the same lockout as wrong
         passwords (S13.7.5).
      4. **Turning it off** in Profile, or an **admin's reset** in Users (for someone who
         has lost both the app and the codes), removes the seed and the codes; the reset also
         ends that user's sessions. Each, and turning it on, is emailed to the user and
         recorded in Activity, as is a sign-in with a recovery code. Each needs the password
         again under S13.7.2.
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
      and alerts (S12.11).
      In dev mode they are written to a folder (S17.7).
2. **Admins are not superusers of money.** An admin manages users, groups and Settings, and
   sees only the accounts and portfolios shared with them. Users are not deleted: a user
   who leaves is made inactive (S10.1.7), and their data stays.
3. **What can be shared**: seven kinds of item, each with one owner and its own list of shares:
   | Kind | A share includes |
   |---|---|
   | **Account** | its transactions, holdings, positions and receipts; a loan's payoff plans and a physical-asset account's items |
   | **Portfolio** | its charts and the accounts in it, as S5.1 says |
   | **Budget** | its categories, plan, actuals and trends (S7.1) |
   | **Person** | their occasions and gifts (S7.8.5) |
   | **Giving plan** | its target, pace, donations and organisations (S7.9.1) |
   | **Tax book** | its panels, filings and documents (S8.14.3) |
   | **Projection** | its inputs, results and tracking (S6) |

   Each can be shared with a **user** or a **group**, at:
   1. **read**: see everything about it. A read share cannot change it, attach receipts or
      re-share it.
   2. **write**: also change what the item holds: for an account, add and edit transactions,
      import, categorise and attach receipts; for the other kinds, edit their entries. A
      write share cannot delete the item, change its sharing, or see or change its secrets
      (keys and credentials), which stay the owner's.
   3. **People on linked servers**: any of the seven kinds can also be shared with named
      users of a linked server (S11), always **read**. Each server sends its peers its list
      of active users (display name, username and email), so they can be chosen like local
      users. Groups are not sent. When a remote user is deactivated, their shares are
      suspended. When the link ends, the shares are removed.
      1. **A remote user is a `User` record** with its `linkId` set, so it appears wherever
         a share is chosen, beside local users, under its server's name. It has no password,
         two-step or sessions (a `CHECK` enforces it), and its fields come only from its
         server (S11.3).
      2. **Only local users** appear where a user signs in, owns or changes something here:
         sign-in, Users and Groups, group membership (a group can hold write shares, and a
         remote user only ever reads), the Admins group, tax-book filers (S8.14.1), the
         spouse for wash sales, the owner of anything, and who receives alerts (S12.11). A
         person on the Gifts screen can be linked to a user of either kind (S7.7.1).
      3. **Settings › Linked servers** lists each link's users, read only.
4. **The Share dialog** lists every active user, then every active group, then the people on
   each linked server, each list alphabetical under a heading with a line on what sharing
   gives. Local users and groups have a three-way switch **None · Read · Write**. People on
   a linked server have **None · Read**, under the server's name, which notes that it
   confirms who they are. Each linked server with anyone set to Read has **Include
   receipts** (off by default, S11.5). A user who has access only through a group is shown
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
   own window (S12.10).
8. **Activity** lists the changes worth showing, each naming who made it and what it is about,
   to the people concerned (the owner, the receivers, and admins for users and groups): shares given or taken away, accounts created, closed
   or deleted, imports, rule changes, links made or ended, and who did each. Amounts are
   never named (R3.8).
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
      (S11.9).
   4. A token works only at `/mcp`, never at `/ui/api`. It stops when it is revoked or
      expires, and when its user is made inactive. Each call is recorded in Activity under
      the token's name, and calls are limited to 60 a minute per token.
