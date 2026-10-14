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
