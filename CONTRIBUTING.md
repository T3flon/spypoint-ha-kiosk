# Contributing

Thanks for taking a look. This project scratched one person's itch - getting SpyPoint trail camera photos onto a Home Assistant wall display - and it is maintained in spare time. Contributions are welcome, and so are bug reports that simply tell me something does not work on your setup.

## Before you open an issue

Most problems with this project fall into a handful of categories, and the README already covers several of them. Please skim the **Known pitfalls** section first - the silent cron failure and the expiring photo URLs in particular have bitten people before.

## What to include in a bug report

This project touches four moving parts (SpyPoint's cloud, a Python script, cron, and Home Assistant), so a report without context is hard to act on. Please include:

- **Home Assistant version** and how it runs (Docker, HAOS, supervised, core)
- **Your SpyPoint camera model** - the API behaves differently across models
- **Where the script runs** (same host as HA, separate machine) and how the photo folder reaches Home Assistant
- **What you expected and what happened instead**
- **Relevant output**: the script's output when run by hand, and anything from journalctl -u cron if the problem is with scheduling

Please remove your SpyPoint username, password and any photo URLs before pasting logs. Photo URLs contain signed access tokens.

## Pull requests

Small, focused pull requests are much easier to review than large ones. If you are planning something substantial, open an issue first so we can agree on the direction before you spend time on it.

A few things that help:

- Keep the existing style of the script rather than reformatting it wholesale
- Do not add dependencies unless they genuinely earn their place - the script deliberately gets by with pyspypoint and requests
- If you change behaviour that the README describes, update the README in the same pull request
- Test against a real camera if you can, and say in the pull request which model you used

## Ideas that would be genuinely useful

If you are looking for something to work on:

- Support for more than one camera on the same account
- A cleaner way to handle the photo retention (right now old files simply accumulate)
- Making the script survive a SpyPoint API change more gracefully instead of failing silently
- Documentation for Home Assistant OS installs, where the Docker volume approach does not apply

## Code of conduct

This project follows the Contributor Covenant. See CODE_OF_CONDUCT.md.

## Licence

By contributing you agree that your contribution is licensed under the MIT Licence, the same as the rest of the project.
