@@ overview

> A self-custody bitcoin wallet, read from its extended public key or addresses. MoneyKata can
> see it, never spend from it.

@@ settings

## Keys and addresses

The wallet's extended public keys and addresses, and the addresses watched.

## Extended public keys or addresses {#wallet-keys}

An **xpub** (legacy addresses, 1…), **ypub** (nested segwit, 3…) or **zpub** (native segwit,
bc1q…), or addresses, one a line. Taking a key out stops watching its addresses.

> Never enter a seed phrase or a private key: the form clears anything that looks like one at
> once, and MoneyKata never stores or logs it.

## Gap limit

How many unused addresses past the last used one are watched on each chain. 20 suits most
wallets.

## Watched {#watched}

How many addresses are watched and how many have been used, and when the explorer or node in
Settings › Bitcoin last checked them. **Addresses** lists them: receive and change, by index.

## Check now

Reads the wallet from the explorer or node in Settings › Bitcoin now, rather than at the next
hourly check. Each confirmed transaction is recorded once: bitcoin received as a transfer in
(enter its cost basis from the Transactions tab, or Taxes shows it as missing), and bitcoin sent
as a transfer out, its network fee included. A transfer out that was a sale or a payment can be
changed to one.
