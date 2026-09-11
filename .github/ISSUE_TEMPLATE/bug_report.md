---
name: Bug report
about: Something does not work on your setup
labels: bug
---

**Before you start:** please skim the Known pitfalls section of the README. The silent cron failure and the expiring photo URLs account for most reports.

## What happened

What did you expect, and what happened instead?

## Where it breaks

Which part of the chain fails? Tick what applies:

- [ ] The script does not download anything
- [ ] The script downloads, but the files never appear in Home Assistant
- [ ] The camera entities stay unavailable or show an old photo
- [ ] The push notification does not arrive, or arrives without an image
- [ ] The dashboard view does not render
- [ ] Something else

## Setup

- Home Assistant version:
- How Home Assistant runs (Docker / HAOS / supervised / core):
- SpyPoint camera model:
- Where the download script runs (same host as HA / separate machine):
- How the photo folder reaches Home Assistant (Docker volume / network share / other):
- Operating system of the machine running the script:

## Output

What does the script print when you run it by hand?

If the problem only happens on the schedule and not by hand, please also check journalctl -u cron - a failing job often leaves no other trace.

**Please remove your SpyPoint username, password and any photo URLs before pasting.** Photo URLs contain signed access tokens that grant access to your images.

## Anything else

Screenshots of the Home Assistant side (entity state, logbook, automation trace) are often more useful than a description.
