# MoneyKata: working rules

## Keep the mockup in step with the requirements

`docs/mockups/MoneyKata-mock.html` is the reference for every screen. Any change to
`docs/requirements.md` that touches what a user sees or does (a screen, field, button, dialog,
setting, state, message, or the order of any of them) updates the mockup **in the same
change**. That includes its help-pane guides (`GUIDES` in the file), its sample data, and the
MOCK pill's menu when a new screen, dialog or state needs a way to reach it. A change that only
touches the server's internals needs no mockup change. Say so when you skip it.

Before calling a change done:

1. Open every screen, tab, Settings section and dialog in a headless browser, and fail on any
   page error or console error: `python docs/mockups/check.py shots/` does this and writes
   a screenshot of each to `shots/` (it needs Playwright for Python and its Chromium).
2. Look at screenshots of what changed.

The mockup's `html` element carries `zoom: 2`. Viewport units, breakpoints and pointer
positions in it account for that, so check and screenshot at 2880×1800 (what a 1440×900
window shows).

The web app and its mockup are for desktop browsers. Phone layouts are not checked or fixed:
phones will get a separate, focused PWA later (requirements §15.8).

While the app is being built there are two mockups (requirements §15.9): the hand-written
`MoneyKata-mock.html`, which stays the design reference and is updated with every UI-facing
change, and `MoneyKata-app.html`, generated from the app by `web/ui/mockup/build.py` for the
screens built so far, which `web/check` keeps current.

## Requirements are a statement, not a changelog

`docs/requirements.md` says what MoneyKata is and does, in the present tense. It carries no
dates of decisions, no "now", "no longer" or "revised", and no record of what changed: git
holds the history. When an open question (§21) is answered, the answer goes into the section
it belongs to and the question is removed, renumbering §21 and the references to it. An idea
that was weighed and turned down goes to **Rejected ideas** at the end, with the reason, so it
is not raised again without a new one. `docs/schema.md` follows the same rule.

The **Gaps** section (§22) tracks areas named but not yet specified, each with a lasting id
(G1, G2, …). When a gap is specified, the text goes into its section and the gap's row is
removed; its id is never reused, and new gaps take the next number.

## Free standing

This repository is self-contained. Docs, mockups and code describe MoneyKata in its own terms
and never refer to other projects as the source of a design or behaviour.

## Schema conventions

`docs/schema.md` sets the database's naming and ID rules. A new table with an `id` gets a row
in its prefix table, kept sorted by prefix, in the same change.
