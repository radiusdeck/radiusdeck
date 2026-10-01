# Security Policy

## Supported versions

Security fixes are applied to the latest release and the current `main` branch.
Older releases may require upgrading to receive a fix.

## Reporting a vulnerability

Report suspected vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/radiusdeck/radiusdeck/security/advisories/new).
Do not open a public issue or discussion for an undisclosed vulnerability.

Include enough information to reproduce and assess the report:

- the affected release or commit;
- deployment and authentication configuration relevant to the issue;
- reproduction steps and observed impact;
- a minimal proof of concept, when available;
- suggested remediation, if known.

Remove credentials, RADIUS shared secrets, session keys, access tokens,
certificates, private configuration, and identifying log data from the report.

The maintainers will review the report, coordinate remediation and disclosure,
and credit the reporter when requested and appropriate.

For general defects and feature requests that do not have security impact, use
the repository's public issue tracker.
