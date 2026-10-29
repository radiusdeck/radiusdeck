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
