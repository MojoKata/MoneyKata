# S6. Projections

1. **A projection** asks how money will grow and what it will pay for. It has an owner, a
   name, a **goal type** (S6.2), what it is **built on**, and whether it is **active**
   (S6.7). It is shared like an account (S10.3).
   1. **Built on** chosen accounts, a portfolio, or a typed amount for a what-if. Built on
      accounts or a portfolio, it starts from their **current values** each time it opens,
      with their *as of*, and from their allocation by asset class.
   2. **Contributions**: an amount, its frequency, growth per year, and until when. For
      retirement accounts they are capped by the limits of S1.4.
2. **Goal types.** All three use the same models (S6.4).
   1. **Retirement**, for one person or a **couple**: each person's birth year and
      retirement age, and the accounts that are theirs. After retirement come
      **withdrawals** (the 4% rule, a fixed amount rising with inflation, or a percentage
      of the balance) set against **other income**: Social Security from an age, a pension,
      each with its amount. The answer: the **chance the money lasts** to the horizon (age
      95 by default), and the balance by age.
   2. **Education**, for one beneficiary, built on their 529 accounts (S1.8). The
      beneficiary's birth year gives the first year of school. The user sets the years of
      school and the yearly cost in today's dollars: typed, or a shipped average of tuition,
      fees, room and board for public four-year (in-state) and private nonprofit four-year
      colleges, from the National Center for Education Statistics' *Digest of Education
      Statistics* (table 330.10, public domain, updated yearly and shipped with the tax
      tables), and the contributions,
      flagged where one person's gifts pass the annual exclusion (S1.8.2). The answer: the
      projected balance against the cost, the **percentage funded**, and the monthly
      contribution that would fund it fully. A 529's **Goal** tab shows this projection.
   3. **Savings target**: an amount by a date (a house deposit, a car), built on any
      accounts. The answer: the **chance of reaching it** by the date, and the monthly
      saving that would.
3. **Assumptions**, kept once per user in **Profile › Assumptions**: expected return and
   volatility for each asset class (US stocks, international stocks, bonds, cash, crypto,
   real estate, metals), general inflation (2.5% by default) and education inflation (5% by
   default). Every projection uses them unless it overrides a figure, so the user's
   projections and the payoff planner (S6.10) agree with each other. Fees per projection.
   1. **Bitcoin models.** For the bitcoin in what a projection is built on, the user can
      choose a published model in place of the crypto assumption, in Profile › Assumptions
      or per projection. Other coins keep the crypto assumption. Each model gives a median
      path from today's price and a range around it:

      | Model | What it is | Its range |
      |---|---|---|
      | **Your assumption** (the default) | log-normal at the crypto return and volatility above | the Monte Carlo fan |
      | **Power law** (Santostasi) | price = A × (days since the genesis block)^n, n ≈ 5.8 | the fit's spread, about a factor of two either way |
      | **Log regression** (the "rainbow chart") | a logarithmic curve fitted to the price history | its bands, from the fitted lows to the fitted tops |
      | **Stock-to-flow** (PlanB) | value from the ratio of supply to new issuance, stepping up at each halving | its published band |
      | **Saylor, Bitcoin24** (2024) | $3M, $13M and $49M by 2045 (bear, base, bull) | the bear and bull cases |
      | **ARK Invest** (2030 targets) | $500K, $1.2M and $2.4M by 2030 (bear, base, bull) | the bear and bull cases |

      1. **Compare models** shows every model's median path on one chart (log scale) with
         the price history behind it, and a table of each model's figures for 2030, 2035 and
         2045.
      2. **Each model states its source and record.** Stock-to-flow has run below its own
         band since 2022; the targets of Saylor and ARK are forecasts by people with a stake
         in the outcome; the curve fits describe the past and say nothing about why it
         should continue. MoneyKata shows these as models others publish, not as its own
         view, and not as advice (R1.16).
      3. **Their figures ship with the app**, dated and with their source, in Settings ›
         Tax tables, and are updated with it (a new ARK target, a refit of the power law).
      4. A projection that uses a model with bear, base and bull cases shows those three
         paths in place of a fan, since they are not percentiles.
4. **Models:**
   1. **deterministic**: future value at a constant rate, in nominal and today's dollars;
   2. **Monte Carlo**: *N* runs (1000 by default) drawing yearly returns from the asset
      classes' mean and volatility (normal or log-normal; historical bootstrap later), showing
      the 10th/50th/90th percentile **fan** and the type's answer (S6.2).
   3. **Glide path** *(later)*: the allocation shifting toward bonds as the goal nears, as
      age-based 529 portfolios and target-date funds do.
5. **Tax-aware buckets** (later): taxable, deferred and free balances projected apart, with
   RMDs from the required age and an assumed tax rate on withdrawals.
6. **Scenarios compare** side by side, for example retiring at 60 against 65, or contributing
   $500 more a month. Projections that are not active are the scenarios.
7. **Active projections** are the plans being followed.
   1. **At most one per subject**: one retirement projection per person or couple, one
      education projection per beneficiary, one per savings target. Making one active asks
      before turning off the one it replaces.
   2. **The baseline**: making a projection active stores its median path and its 10th–90th
      percentile band as of that day.
   3. **Tracking**: the actual balance of what it is built on, plotted against the baseline
      to date, and a status: **on track** inside the band, **ahead** above it, **behind**
      below it. Beside it, the type's answer run again from today's balance.
   4. **Changing an active projection's inputs** asks whether to **re-baseline**. Without
      it, tracking keeps comparing against the plan as it was made active.
   5. **Falling behind** raises an alert (S12.11), checked monthly, and resolves when the
      balance is back inside the band.
8. **Where active projections show:**
   1. the **Dashboard's Plans** card: one row each, with the type and name, the status, the
      type's headline figure (*87% chance of success*, *64% funded*, *$28,000 of $40,000 by
      2028*), and a small chart of the actual balance against the baseline;
   2. **on what it is built on**, when that is one account or one portfolio: a 529's Goal
      tab, an account's Overview, or a portfolio's *Projections* tab. A projection built on
      several accounts shows only on the Dashboard and the Projections screen;
   3. an active projection **shared with you** shows on your Dashboard only when you tick
      **Show on my Dashboard** on it, which is off by default, as **Count in my totals** is
      for accounts (S10.7). A linked household's projections show only in its window
      (S12.10).
9. **The computation runs on the server**, seeded so a scenario's figures are
   reproducible, and returns percentiles per year. It uses NumPy. The screen states its
   assumptions in full under the chart and says plainly that it is a model, not a forecast.
10. **Loan payoff planner** (on each loan's *Payoff* tab, S1.9.5). It compares the schedule
    with the user's **overpayment** plans:
    1. **Plans**, combined freely: an extra amount every month (from a date, until a date),
       an extra amount once a year (a bonus month), one-time **lump sums** on dates,
       **biweekly** payments (26 half-payments a year), and rounding each payment up.
    2. **Results** for each plan against the schedule: the new payoff date, months saved,
       **interest saved**, total paid, and the balance over time as two lines on one chart,
       with the amortization table of each.
    3. **Recast**: after a lump sum, a mortgage can be **recast** (the term kept, the payment
       lowered) instead of shortened. The planner shows both, with the servicer's recast fee.
    4. **Against investing the extra**: the same money invested at the user's expected
       return (S6.3) shows its value at the payoff date next to the interest saved.
       It is a comparison, not advice, and says so (R1.16).
    5. **Saved plans** are kept per loan. One can be marked **the plan I'm following**, and
       the loan's screen then shows whether actual overpayments are ahead of it or behind.
    6. Rates for an ARM's future resets are the user's assumption, shown as such.
