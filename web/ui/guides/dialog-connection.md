# New connection

A sign-in at one institution, kept by the MoneyKata Connector. What you type is encrypted in
your browser for the connector before it is sent: MoneyKata keeps only what it can't read, until
the connector collects it, and never shows it back.

## Institution {#driver}

Which driver fetches it: **Schwab** (its official Trader API, signed in on Schwab's own page),
**OFX Direct Connect** (a bank or credit union that still runs an OFX server, with a username
and password), or **a folder of downloads** on the connector's host, which needs no sign-in at
all.

## Connection name {#label}

A name to tell it apart: *Schwab login*, *Credit union*.

## Folder on the connector's host {#folder-path}

The folder the connector watches, mounted read only into it: a Downloads folder, for example.
Each statement or export that appears is posted to the account its rule names.

## Rules {#folder-rules}

One per line: a file-name pattern and the last four digits of the account it goes to, such as
`umb-*.pdf → 3311`. A file no rule matches waits in the folder.

## OFX server address {#ofx-url}

The institution's OFX Direct Connect address, from the institution or a directory such as
ofxhome.com.

## ORG {#ofx-org}

The institution's OFX organisation name, as the directory lists it.

## FID {#ofx-fid}

The institution's OFX id, as the directory lists it.

## Account type {#ofx-account-type}

Checking, savings, credit card or investment, as the OFX server expects it.

## Account number {#ofx-account-id}

The account's number at the institution, which the OFX server asks for. It is sealed with the
credentials, never shown here.

## App key {#schwab-app-key}

Your Schwab developer account's app key, which the driver signs in with. It isn't a secret: the
sign-in is.

## How you sign in {#how-you-sign-in}

**Here, sealed for the connector**: the usual way; your browser encrypts what you type to the
connector's key, and MoneyKata can't open it. **An admin types it on the connector's host**: the
stricter way; the dialog shows the command, and MoneyKata never handles the credentials at all.

## The address you landed on {#landed}

After signing in on the institution's own page, the address your browser lands on. It carries
the sign-in for the connector; sealed here like a password. Schwab's lasts seven days.

## Username

Your username at the institution. Sealed for the connector.

## Password

Your password at the institution. Sealed for the connector, never seen by MoneyKata.

## Connect command {#connect-command}

For the stricter way: an admin runs it on the connector's host and types the credentials there.
