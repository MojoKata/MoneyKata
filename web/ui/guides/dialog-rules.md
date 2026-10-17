# Categorisation rules

Your rules for the transactions you import: each says what a payee looks like and what to set
when one matches. They are yours alone, never shared, and never sent to a linked server.

## First match wins {#first-match}

A transaction takes the first rule, top to bottom, that it matches, so a narrow rule goes above a
broad one: `re:^KROGER FUEL` above `kroger`. Move a rule with **↑** and **↓**.

Rules set a category only where there is none, and never touch a split, a transfer between your
accounts or a trade. They run on every file, statement and connector fetch you import, and on the
receipts you add: a rule that renames a payee renames the merchant a receipt names.

**Apply to the uncategorised** runs them now over the uncategorised transactions in the accounts
you can change. Activity records how many it set, never an amount.
