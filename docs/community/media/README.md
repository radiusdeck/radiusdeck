# Client lifecycle demo

[Watch or download the video](client-lifecycle.webm).

The recording shows the real RadiusDeck Community interface in Chromium, with
fictional devices and test-only shared secrets. The captions along the bottom
are explanations added for the video, not part of the application interface.

1. Add `guest-ap-01` with IP address `192.0.2.30` and a masked shared secret.
2. Edit its IP address to `192.0.2.31`, leaving the secret blank to keep it.
3. Verify that the client row immediately shows the new IP, then open **Details**
   to check the saved address without reloading the page.
4. Open **Backups**, select **Restore latest**, and confirm the restore.
5. Return to **Clients** and verify that `guest-ap-01` is back at `192.0.2.30`.

The recording uses an isolated temporary `clients.conf`. Automatic backups are
enabled. FreeRADIUS reload is disabled, and no real network device or RADIUS
server is contacted. This demonstrates file editing and recovery, not a live
authentication test.

Rollback restores the entire configuration from before the IP edit, so the
newly added device remains present. The capture script verified that the
restored file exactly matched the configuration after device creation and that
the shared secret was preserved. A safety backup is created before rollback.

Format: WebM (VP8), approximately 31 seconds, 1440 × 900, no audio.
If GitHub does not play the file inline,
download it and open it in a browser or video player that supports WebM.
