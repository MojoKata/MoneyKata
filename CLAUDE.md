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
   page error or console error.
2. Check that a 390 px viewport has no horizontal scroll.
3. Look at screenshots of what changed.

Once `web/ui` exists, the mockup is generated from the app (`web/ui/mockup/build.py`), and
`web/check` fails while the mockup is out of date (requirements §15.9).

## Free standing

This repository is self-contained. Docs, mockups and code describe MoneyKata in its own terms
and never refer to other projects as the source of a design or behaviour.

## Schema conventions

`docs/schema.md` sets the database's naming and ID rules. A new table with an `id` gets a row
in its prefix table, kept sorted by prefix, in the same change.
