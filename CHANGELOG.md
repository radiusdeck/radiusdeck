# Changelog

Notable changes to RadiusDeck Community. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **+ Add field** and **+ Add block** in the New Client and Edit forms, and
  the buttons of a nested block, now add a row. In 0.1.0 and 0.1.1 they
  inherited the form's `hx-select`, so nothing was inserted.
- **Add Client** with the name of an existing client no longer replaces that
  client. The file is left unchanged and the form reports that the client
  already exists; use **Edit** to change it.
- An error from **Add Client** is shown as text under the form instead of
  `[object Object]`.
- The client address is checked when a client is added or its address is
  changed. Values that FreeRADIUS 3.2 rejects or reads differently from what
  was typed are refused with the reason: `300.1.1.1`, `192.0.2.010` (read as
  192.0.2.8), `192.0.2` (read as 192.0.0.2), `192.0.2.10/24` (read as the
  whole network), an IPv6 zone. An address or network that another client
  already uses is refused too: FreeRADIUS does not start with duplicate
  clients. Host names and "any address" values (`*`, `0.0.0.0`, `::/0`) are
  saved with a warning. An address already in the file is not checked when
  it is left unchanged.
- Errors from **Save Changes** in the Edit form are shown in the form. The
  server returned them with status 400, which htmx did not display.
- Clients whose address is in `ipv4addr` or `ipv6addr`, such as the stock
  `localhost_ipv6`, show their address in the list, and **Edit** opens for
  them instead of failing with an error 500. Saving changes that key in
  place, and an `ipv6addr` client accepts only an IPv6 address (`ipv4addr`
  only IPv4). These keys cannot be added as extra parameters.

## [0.1.1] - 2026-10-27

### Security

- The web interface no longer loads Bootstrap, htmx, and Lucide from the
  jsDelivr and unpkg CDNs. The application serves Bootstrap and htmx itself,
  so no third-party scripts run on pages that show shared secrets, and the
  interface works on networks without internet access.
- Release assets are signed: the container image and the wheel have GitHub
  build provenance attestations, and the release notes give the image digest
  with the commands to pull and verify it.

### Changed

- Bootstrap 5.3.0 is updated to 5.3.8 and htmx 1.9.6 to 1.9.12. The eye icon
  of the shared secret button is an inline SVG; Lucide is no longer used.
- The browser tab title is `RadiusDeck` instead of `FreeRADIUS Manager`.
- FastAPI is updated from 0.143.0 to 0.161.1.
- Third-party licenses are listed in `THIRD-PARTY-NOTICES.md`, which is
  included in the wheel and the image.

### Documentation

- The README describes installing the published Docker image, privacy and
  network access, and how to get help.
- `SUPPORT.md` and GitHub issue forms for questions and bug reports.

## [0.1.0] - 2026-10-14

First public release of RadiusDeck Community.

[0.1.1]: https://github.com/radiusdeck/radiusdeck/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/radiusdeck/radiusdeck/releases/tag/v0.1.0
