# Linked servers

Other MoneyKata servers that share read-only with this one: another household's, or a
preparer's. Admins only.

![Linked servers](shots/settings-links.webp)

**Invite a server** makes a one-time code for the other server's admin. **Enter a link code**
answers one: MoneyKata connects to the address in the code, checks the server's key against the
fingerprint in it, and asks to link. The inviting side then lists it as **wants to link**: compare
the fingerprint shown with what the other admin sees for their own server (by phone, in person)
and **Approve** or **Reject** it.

## This server's link address {#link-address}

Where other servers reach this one, as `https://…` without a path: MoneyKata answers them under
`/link/`. It must be reachable from the other server: a forwarded port, a reverse proxy that
passes `/link/`, or both servers on one overlay network such as Tailscale or WireGuard (the easy
way, with no open port). Empty, the public URL is used.

A link works when either side can reach the other: each exchange carries both directions.

Each link shows its state, its fingerprint and MoneyKata version, and when the last exchange
worked. **Pull now** exchanges at once rather than at the next hour. **Pause** stops this side
exchanging until **Resume**. **End link** ends it on both sides: the other side learns at once, or
at its next call; its users are removed here, and nothing is deleted on the server that shared.
A server that can't be reached shows **unreachable since** and the reason.

## Linked copies {#linked-copies}

What each link brings in is kept apart from this household's data, in its own encrypted copy under
its own **access key**: 12 words. This server's master key can't open it, and backups leave it
out. **Create the access key** once the link is active: MoneyKata shows the words once, for the
household's password manager, where the people its shares name can reach them. Pulls into the copy
begin then.

The first person its shares name who opens the household's window enters the words; the copy then
stays unlocked for everyone it shares with, each seeing only what names them, until it goes unused.
Each copy shows its size, when its key was made and by whom, and who unlocked it. **Lock now**
locks it at once. **Reset copy** (if the words are lost) deletes the copy and its key: make a new
access key, and everything is pulled again from the other server, where nothing was lost.

## Release linked keys after {#link-release}

How long an unlocked copy's key stays in memory with nobody viewing it: 15 minutes, 1 hour (the
default) or 4 hours. Background work, such as a pull, doesn't count as viewing. A restart locks
every copy.

## Users on linked servers {#linked-users}

Each linked server's active users, sent at every exchange and updated in place: a new user is
added, a changed name or email is updated, and a user no longer on the list is removed (and comes
back if they return). People here can share with them, always read only. They never sign in here,
join a group, own anything or receive alerts.
