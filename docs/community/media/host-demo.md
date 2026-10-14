# FreeRADIUS demo recording

[Watch or download](host-demo.webm) · [Run it yourself](../../../demo/README.md)

The video shows a full client lifecycle against a real FreeRADIUS server:
add a client, restart FreeRADIUS, authenticate with `radtest`, rotate the
shared secret, and roll back from a backup.

## What is real and what was added

The left panel is the real RadiusDeck Community interface in Chromium. The
right panel shows the output of real commands run on the same machine; RADIUS
replies are not simulated. Repeated request packets may be shortened in the
panel; such cuts are marked.

The outer frame, the terminal panel, highlighting, and the captions were added
for the video. They are not part of RadiusDeck.

## Setup

The recording follows the steps in [`demo/README.md`](../../../demo/README.md):

- FreeRADIUS on `127.0.0.1:18120` and RadiusDeck on `127.0.0.1:18080`, both as
  ordinary foreground processes;
- `DEMO_STATE` pointed to a temporary directory instead of `demo/host/.state`,
  so config, backups, and logs were deleted after recording;
- FreeRADIUS restarted by hand after each change; the reload sidecar was off;
- the server unpacked from the Ubuntu package, as described in the demo's
  "Run the server without installing" section; no system packages were
  installed and no system services were started or changed.

All names, passwords, and secrets in the video are public test values.

## Checks during recording

| Moment | Result |
| --- | --- |
| Before adding the client | No `Access-Accept`; server log: unknown client |
| After adding and restarting | `Access-Accept` with `demo-secret-v1` |
| After changing the secret and restarting | `Access-Accept` with `demo-secret-v2` |
| Old secret after the change | No `Access-Accept`; server log: invalid Message-Authenticator |
| After restoring the backup | `clients.conf` matches its contents right after the client was added |
| After the final restart | `Access-Accept` with `demo-secret-v1` |

## Recording details

- Ubuntu 24.04, FreeRADIUS 3.2.5, RadiusDeck Community from the commit that
  added `demo/`.
- WebM (VP8), 58 seconds, 1920 × 1080, English captions, no audio.
- [`host-demo.png`](host-demo.png) is a frame from the video.

If GitHub opens a file page instead of a player, click **View raw** or download
the file and open it in a browser.
