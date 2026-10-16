# MoneyKata is locked

The server has started and holds no key: the master key is the recovery phrase, which is
never stored. Until an admin enters it, the server serves this screen and nothing else, and
nobody can sign in. It locks again at every restart.

## Recovery phrase

The 12 words from the recovery sheet, in order, with spaces between them. Four letters of each
word are enough. The eye button shows what was typed. The phrase is checked against the
server's keyring: a wrong phrase is refused, and ten wrong ones in a row are refused for a
quarter of an hour. Every attempt is logged.

## Unlock

Opens the server. On the host, `docker compose exec moneykata moneykata keys unlock` does the
same, for an admin who would rather not type the phrase into a browser. Nothing of the phrase
is kept once the data key is unwrapped.
