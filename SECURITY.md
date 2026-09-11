# Security Policy

## Supported versions

This is a small hobby project maintained by one person in his spare time. Only the latest release on the main branch receives fixes.

## Reporting a vulnerability

Please do not open a public issue for security problems.

Use GitHub's private vulnerability reporting instead: go to the Security tab of this repository and choose "Report a vulnerability". If that is unavailable, contact the maintainer through https://github.com/T3flon.

Expect a first reply within a few days. This is a spare-time project, so please be patient.

## Credential handling - read this before you deploy

This project needs your SpyPoint account credentials, and the photos it downloads can be sensitive. A few things worth knowing:

- **Never put your username and password directly into the download script.** The README shows how to keep them in a separate file outside the repository.
- **Keep that credentials file readable only by your own user** (chmod 600). Anyone who can read it can log into your SpyPoint account and see every photo your camera has taken.
- **Downloaded photos are not encrypted.** Trail camera images can reveal where you live or hunt, and they usually carry a timestamp. Treat the photo folder as sensitive data.
- **Point allowlist_external_dirs at the photo folder only**, never at a parent directory. It grants Home Assistant read access to everything below it.
- **If your Home Assistant is reachable from the internet**, the photos are served under the /media/local/ path to any authenticated user. Review who has an account on your instance.

## Scope

This project is a downloader script plus configuration examples. It does not run a server and accepts no incoming connections. The realistic risk here is credential or photo exposure through misconfiguration, not remote code execution.

The SpyPoint cloud API itself is not part of this project. Issues with the API or with the unofficial pyspypoint client belong in their respective projects.
