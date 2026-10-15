# S7. Budgets, gifts and giving

1. **Budgets are per user, or per group** (a household budget a group shares at `write`).
   A budget covers chosen accounts and is monthly by default, or yearly per category.
   1. **Shared like an account** (S10.3): its owner chooses its accounts, shares it, and
      deletes it; a `write` share also changes its plan. Its actuals count every
      transaction in its accounts, whoever can see them.
   2. **The plan holds from a month on.** A change applies from the month it is made in,
      so past months keep the plan they had; a category taken out of the plan stops from
      that month. A plan line on a parent category counts its children with it.
2. **Categories** form a two-level tree (*Housing › Rent*). Each is an expense, income or
   transfer category. A default set ships, and each category may carry a **tax tag**
   (charitable, medical, business, childcare, education, …) that feeds Taxes (S8.5), and
   **Keep receipts for** a number of years, empty for ever (S14.10.1).
3. **Each period** has, per category, the **planned** amount, the **actual** from
   categorised transactions, and what remains, with optional **rollover** of the unspent or
   overspent remainder to the next period. Spending shows as an amount spent, income as
   received; a split transaction counts through its splits; matched transfers and transfer
   categories never count (S1.7). A yearly line compares with the year to date and does not
   roll over. Spending in a category with no plan is listed as *not in the plan*.
4. **Screens**: the month's categories as progress bars (green, then amber at 90%, red over),
   income against spending, cash flow (a Sankey from income to categories), trends of a
   category over 12 months, and the uncategorised transactions to sort.
5. **Recurring** transactions (rent, subscriptions, salary) are detected from history and
   listed with their next expected date and amount. A missed or changed one is flagged.
   1. **A series** is three or more transactions in one account with the same payee (its
      reference numbers aside) and sign, at a weekly, two-weekly, twice-monthly, monthly,
      quarterly or yearly interval, give or take a few days, with amounts within half of
      the usual one. They are found in the last 15 months each time the list is shown.
   2. **Missed**: the next one is more than a few days late. **Changed**: the last amount
      moved 5% or more from the usual, flagged only where the amounts are otherwise fixed
      (a subscription, rent), since a utility bill varies anyway.
6. **Budget alerts** *(later)*: a category passing a threshold, a large transaction, a low
   balance, raised as alerts (S12.11).
7. **Gift plans and occasions.** People are the household's (S10.10). On the Gifts screen
   each user keeps a **gift plan** for each person they give to or receive from:
   1. **A gift plan has** its person, the **holidays** they get gifts for, **anniversaries**
      other than a wedding (each with its own date), a yearly **gift budget** or one per
      occasion, a reminder lead time (14 days by default), and notes (sizes, likes, what
      they already have). The person's **birthday**, their **wedding anniversary** (the start
      of a *spouse* relationship) and their relation to the user (*your granddaughter*,
      S10.10.5) come from the person. Adding a gift plan for someone new adds the person
      first, as S10.10.3 says.
   2. **Holidays** ship as a list with their dates computed per year: fixed dates
      (Christmas, Valentine's Day), rule-based ones (Mother's Day, Father's Day,
      Thanksgiving), and lunar or lunisolar ones (Hanukkah, Diwali, Lunar New Year, Eid
      al-Fitr) from shipped tables, plus **custom occasions** with a date of their own.
   3. **Upcoming occasions**: the next 60 days of the dates in the user's gift plans, each with its budget,
      the gifts planned so far, and what is still missing. Those inside their lead time show
      on the Dashboard (*Emma's birthday in 9 days, no gift yet*), and an occasion entering
      its lead time raises an alert (S12.11).
8. **Gifts.**
   1. **A gift** is for one or more people and an occasion (and its year): a description,
      a **status** (*idea*, *planned*, *bought*, *given*), its cost, where it was bought, a
      link, notes, and receipts (S9). A cost is linked to its transaction, or typed. One
      purchase can be split across several gifts.
   2. **Ideas** are gifts without a date: a running list per person, to pick from when an
      occasion comes.
   3. **Gifts received** can be recorded too (from whom, for what), with a **thank-you
      sent** tick.
   4. **History**: per person, what was given in past years (so it isn't given twice) and
      the spending per year against their budget. Per year: gift spending by person and by
      occasion. Gift transactions are categorised *Gifts* in budgets (S7.2).
   5. **Privacy**: gift plans and gifts are their owner's alone. A user may share a gift
      plan (with its gifts) with another user or group, read or write, so a couple plans
      their children's gifts together. A gift for a person who is a user is **never shown
      to that user**, even through a share, so a surprise stays one. For a
      user of a linked server, the owner's server leaves those gifts out before sending, so
      they never reach the other server.
   6. **A deleted person**: gifts bought, given or received stay, still count in past
      spending, and show the person as *Emma (deleted)* (R3.10). Ideas and planned gifts
      for that person alone are deleted with them; a shared idea loses only that person.
   7. **Gift-tax flag**: money given to one person in a year (cash gifts, and 529
      contributions, S1.8.2) above the annual exclusion is flagged for Form 709 (S8.11).
9. **Charitable giving.**
   1. **A giving plan** per year, per user or per group (as budgets are): a **target** as a
      **percentage of income** (10% by default when one is set), or a fixed amount.
   2. **Income**, for the percentage, is one of: the year's transactions in *Income*
      categories (take-home pay, the default), a typed **gross income** (from a W-2 or a pay
      stub), or a typed estimate of AGI. The plan says which it uses.
   3. **Donations** come from transactions categorised under *Giving* (tax tag
      *charitable*, S7.2), or are recorded directly: the organisation, date, amount, and
      **type**: cash (card, cheque, transfer), **goods** (with their fair market value),
      **appreciated securities** (shares from a lot, S2.2: no gain is realized, and the
      deduction is the market value when held over a year, otherwise the basis), a
      **qualified charitable distribution** from an IRA (from age 70½, up to the year's limit
      in the tax tables), a **contribution to a donor-advised fund**, or a **grant** from
      one.
   4. **What counts toward the target**: everything that left the user's hands, with a DAF
      counted when it is funded (the default) or when it grants, as the plan chooses. A DAF
      contribution is never counted twice.
   5. **Organisations**: the name, EIN (optional), whether gifts to it are **deductible**
      (a 501(c)(3) charity, or not, such as a political campaign or a person), causes (tags),
      and **pledges** (an amount a month or a year, shown as expected donations).
   6. **The Giving screen**: given against the target and against the pace to date, the
      projected year end, giving by organisation, cause and type, the DAF's balance and its
      grants, the percentage of income over past years, and the donations missing an
      acknowledgement that the tax rules require (S8.9).
