# S13. Architecture

1. One HTTPS address. `/` redirects to `/ui`. `/ui/*` serves the app and `/ui/api/*` its API.
   `/link/*` is the linked-server API (S11). `/mcp` is the read-only endpoint for agents
   (S10.9). `/healthz` is the health check. `/demo` serves the clickable mockup (S12.9) to
   anyone, without signing in: it holds only sample data, runs in a sandbox with an opaque
   origin, and can reach neither the app's cookie nor its API.
2. **Authentication**: server-side sessions for `/ui/api` (a random token stored hashed, in an
   HttpOnly, Secure, SameSite=Strict cookie, with an `Origin` check on every change; idle and
   absolute lifetimes are Settings). Signed peer requests for
   `/link` (S11.1). Neither is accepted on the other's path.
3. **Port 37373**, on all of the container's interfaces; the host's port mapping and firewall
   decide what reaches it. **Two listener modes**, one switch in `moneykata.toml`:
   **`proxy`**, plain HTTP behind haproxy, Caddy or nginx, which ends TLS (forwarded headers
   are trusted only from the configured proxy addresses); or **`tls`**, its own HTTPS
   listener with HTTP/2 (forwarded headers ignored). **`proxy`** is the expected setup.
   **`tls`** is for testing on a local network: given no certificate, the server makes a
   self-signed one on first start and keeps it in the data directory. It names the server
   and `localhost`, and the names and addresses listed in `[tls] names`, which are how
   browsers on the network reach it; a change to the list makes it again.
4. **Background tasks** in the server process: price refresh (S4.4), bitcoin wallet reads
   (S1.6), link pulls (S11.4), option expiry (S3.6), recurring detection (S7.5), backups
   (S14.6), receipt and statement reading (S9.8, S1.3, in its own worker process), and
   pruning. Each records its last run and error, which Settings shows.
   They run in a thread pool with per-provider rate limits and never block a request.
5. **Outbound calls** go through one httpx client with an **egress guard**: only the hosts of
   enabled price sources, the bitcoin explorer or node, the SMTP server, and links; never
   loopback, link-local or cloud metadata addresses unless an admin allows one by name; with
   timeouts and response-size ceilings. Email goes through the standard library's SMTP
   client, past the same guard; its host is one an admin named in Settings › Email, so it
   counts as allowed by name.
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
      S16.5, and no other rules. Checked against a shipped list of the 100,000 most common
      passwords, which are refused.
   4. **Cross-site requests**: `SameSite=Strict` plus an `Origin` check on every request
      that changes something; a missing or foreign `Origin` is refused with 403. No CORS: the
      API answers only its own origin.
   5. **Rate limits**, per client address and per user, answered with 429 and a
      `Retry-After`:
      1. sign-in, two-step codes and password-reset requests: 10 failures in 15 minutes lock
         that username for 15 minutes and slow that address (S10.1);
      2. linked copies' access keys: S11.9.3.3;
      3. the API: 600 requests a minute per session; uploads: 60 files an hour per user;
      4. `/mcp`: 60 calls a minute per token (S10.9.4); `/link`: 60 calls a minute per
         link.
   6. **Request limits**: JSON bodies up to 1 MB, uploads up to the size in Settings
      (25 MB by default), at most 100 MB of uploads in flight per user, and request headers
      up to 16 KB. Each upload's type is checked from its content, never its name (S9.1).
   7. **Response headers** on every response: the CSP of S17.3.3,
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
      user ids, record ids, routes and outcomes only (R3.8). Sign-ins, failures, lockouts and
      every admin action are logged and recorded in Activity.
   10. **TLS** (in `tls` mode): TLS 1.2 and 1.3 only, with the server's default modern cipher
       suites; HTTP/2.
   11. **Supply chain**: Python dependencies pinned with hashes in `uv.lock`; browser
       libraries vendored with their hashes in `manifest.json` (S17.3.1); the image built
       from a pinned base and rebuilt for security updates.
8. **API conventions** *(proposed, for review)*, for `/ui/api` and, where they apply, `/mcp`.
   The OpenAPI document is generated from the routes (R3.9).
   1. **Resources and methods**: plural nouns (`/ui/api/accounts`, `/ui/api/accounts/{id}`).
      `GET` reads, `POST` creates, `PATCH` changes the fields it sends, `DELETE`
      soft-deletes (`schema.md` §4) and returns 204. An action that is not a change of
      fields is a `POST` to a verb under the resource (`/ui/api/links/{id}/pull`).
   2. **Names and values in JSON**: field names camelCase, as in the database (`schema.md`
      §1). Ids are the prefixed strings of `schema.md` §2. Money is a decimal **string** in
      dollars with two places (`"1234.50"`); quantities and prices are decimal strings to
      their own scale (S14.3); floats are refused. Dates are `YYYY-MM-DD`; timestamps are
      RFC 3339 in UTC (`2026-10-12T14:05:00Z`, S14.9). A field with no value is `null`, never
      left out.
   3. **Errors** are `application/problem+json` (RFC 9457): `type`, `title`, `status`,
      `detail`, the error id of S13.7.8, and `errors`, a list of `{field, code, message}` so
      the UI shows each refusal at its field (R3.7). Codes are stable strings
      (`key-too-short`, `share-not-allowed`), listed in the OpenAPI document.
   4. **Status codes**: 200, 201 with `Location`, 202 for work that continues (S13.8.7),
      204, 400 for a malformed request, 401 when not signed in, 403 when not allowed, 404 for
      what doesn't exist *or* isn't visible to the caller (never revealing which), 409 for a
      conflict, 412 for a stale version, 413, 415, 422 for a valid request that breaks a rule,
      429, and 503 while the server is starting or a linked copy is locked.
   5. **Paging**: by cursor. `?limit=` (100 by default; 500 and 1000 allowed, S12.1.3) and
      `?after=<cursor>`; the response has `items` and `next` (a cursor, or `null`). Sorting
      with `?sort=field` or `-field` on the fields each list declares; filters as named query
      parameters.
   6. **Concurrency**: each record has a `version` that changes with every save. `PATCH` and
      `DELETE` send it in `If-Match`; a stale one gets 412 with the current record, so the UI
      can show what changed.
   7. **Long work** (an import, a statement read, a projection run, a reset copy) answers
      202 with a job resource (`/ui/api/jobs/{id}`: state, progress, result), and the live
      stream announces its end (S12.6).
   8. **Idempotency**: a `POST` that creates may carry `Idempotency-Key`; a repeat within 24
      hours returns the first answer. Imports are idempotent by their content (S1.3).
   9. **Versioning**: `/ui/api` is served with the app and changes with it, so it carries no
      version; the OpenAPI document states the release. `/mcp` and `/link` are versioned in
      their own protocol (G1, G7).
   10. **Visibility**: every read goes through the caller's shares (S10.3) and the soft-delete
       views (`schema.md` §4.2). A list never counts or hints at what the caller can't see.
