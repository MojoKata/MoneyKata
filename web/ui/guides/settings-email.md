# Email (SMTP)

How MoneyKata sends its emails: invitations, password resets, sign-up links and decisions, alerts. Until a host is set, each email is written to the `mail` folder in the data directory instead, where an admin can open it.

Emails go out in the background, so nothing waits on the mail server. One that can't be sent stays queued and is tried again every five minutes; this section shows the queue and the last error.

## Host {#smtp-host}

The mail server's name, such as your email provider's SMTP server or a relay on your network. MoneyKata reaches only this host for email.

## Port {#smtp-port}

587 for STARTTLS, 465 for TLS, 25 for a plain relay.

## Security {#smtp-security}

**STARTTLS** and **TLS** encrypt the connection and check the server's certificate. **None** sends in the clear: only for a relay on your own network.

## Username {#smtp-username}

The account to sign in to the mail server with, often an email address. Leave it empty for a relay that needs none.

## Password {#smtp-password}

Kept encrypted as a secret, used only when sending, and never shown again. Many providers want an app password rather than your own.

## From address {#smtp-from}

The sender emails show, such as `MoneyKata <money@example.com>`. Your provider may insist it matches the username.

## Send a test email

Sends one to your own address now, through the saved settings, and says what failed if it couldn't.
