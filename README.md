# Setlist for Windows

VirtualDJ playlist studio and app updates. The `website/` folder contains the existing website; `setlist/` contains the desktop source for **1.7.22**.

## Desktop behavior

Version 1.7.22 keeps Music to Find in a compact glass popup matching the playlist maker. The header and controls stay fixed while songs scroll, without a visible scrollbar. Song information, status and pill-shaped YouTube action stay together; the close icon is centered and content stays inside the rounded corners. Whole song lists can be pasted and previewed before saving. Spotify playlist URLs use the existing Spotify connection; standard text/URI link drops are supported, with a copy-link fallback for unsupported drag formats.

Chrome companion **1.0.2** restores and focuses the selected normal Chrome window on every real song click, while reusing the same YouTube tab. The temporary Windows foreground handoff is restricted to the connected Chrome process. No browser security settings, remote debugging or permissions are broadened.

Version 1.7.18 adds a separate **Music to Find** checklist. It preserves the original order and repeated entries, stores dated checks independently in `music-to-find.json`, and shows Have / Needs checking / Not found with coverage and version notes. Recheck reads the selected music folder without changing files or performance playlists. Cancelled or failed checks retain the prior results. No music acquisition or downloading is implemented.

Version 1.7.20 fixes YouTube reuse while a committed page is still loading. The app retains only the latest queued click during a handoff instead of discarding later song requests. The Chrome companion is version 1.0.1, with unchanged permissions.

Version 1.7.19 makes Music to Find compact: inline title/artist, reduced spacing and counters, collapsible evidence, and pill-shaped YouTube buttons. All evidence remains available under Details; recording preferences and statuses remain visible. Stored checklist and playlist formats are unchanged.

YouTube searches use the approved Chrome companion in the user's normal Chrome profile. It remembers one YouTube tab and reuses its ID; a closed tab is safely replaced. If several YouTube tabs are available, choose one in the companion popup. A tab navigated away from YouTube is released. Connection errors show a copyable search address without silently opening extra tabs. The former Setlist WebView listening window is removed. See [Chrome companion setup and boundaries](docs/chrome-tab-reuse-proposal.md).

Describe a playlist or import a song list, review local matches, then explicitly approve adding the playlist to your selected DJ destination. Local playlist matching uses metadata and play counts, not AI or audio similarity. MP3/MP4 recordings are eligible; recognizable karaoke is excluded. Unchecked content preferences are neutral. Unknown content labels and insufficient local matches remain visible.

Artist-style requests are distinct from by-artist requests. Conservative typo handling automatically corrects only confident, unambiguous names. Playlist adjustments preserve selected and favorite songs. Duration requests use an estimated DJ play time of up to 1:45 per song plus 25% spare choices, separately from full-file runtime.

Version 1.7.17 defaults new pasted lists to **Song title - Artist** and retains the explicit **Artist - Song title** option. Prepared Spotify/photo text and restored saved entries retain their explicit format. Existing playlists and the VirtualDJ export mapping are unchanged.

Version 1.7.15 moves the existing approval action beside Close, fixes exclusive navigation highlighting, balances review gutters, and estimates processing time only from credible measurements of current-stage work. Matching animation follows actual result events and never delays completion.

## Develop and test (Windows 10/11, 64-bit)

Requires Python 3.12, Node.js 22, and Microsoft Edge. In PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
.\scripts\test.ps1
```

The test script runs 205 Python tests and thirteen JavaScript regression suites with a temporary isolated app profile and ephemeral port. It does not use your installed Setlist profile. Real music-library fixtures, profiles, credentials, and private verification reports are intentionally absent from this repository.

To run source without touching your normal profile:

```powershell
$env:SETLIST_DATA = Join-Path $env:TEMP 'setlist-dev-profile'
$env:SETLIST_PORT = '0'
python setlist/app.py
```

Build the local Windows OCR helper and packaged executable:

```powershell
.\scripts\build.ps1
```

The build uses the Windows .NET Framework compiler and Windows Runtime metadata, then creates `dist/Setlist.exe` with PyInstaller. Compiled binaries are ignored by Git. Building does not install, publish, or replace a running app. Release publication remains a separate explicit action. `setlist-installer/setup.py` is the legacy installer retained for regression coverage. The 1.7.22 release uses the established `Setlist.exe` and `setlist-update.json` distribution; it does not claim to include a new full-app installer. The optional Chrome companion is a separate manual setup package, described below.

Photo OCR runs locally through Windows OCR. Spotify imports and optional catalog discovery retain their existing external-service behavior; no music files are uploaded by playlist matching. Spotify account approval and supported Windows OCR languages are required for those respective features.

## Validation

Version 1.7.22 passed the automated suites, packaged UI checks in light/dark, short and narrow layouts, real mouse-wheel/Page Down scrolling, bulk-paste preview, and installed-executable checks. Three successive real song clicks and minimized-window recovery reused one YouTube tab and verified Windows foreground. Saved data was compared against a pre-update backup. Physical touch/touchpad hardware and live Spotify intake were not exercised in this release check. No repository CI is currently enabled. `docs/desktop-workflow.example.yml` provides a Windows GitHub Actions template for the same synthetic regression tests and packaging; enabling it requires workflow-write permission. It cannot reproduce private-library or interactive desktop acceptance checks.

## Release and Chrome companion

Download `Setlist.exe` through the existing in-app updater; `setlist-update.json` contains the matching SHA-256. The app update does **not** silently install or update a Chrome extension. Download `Setlist-Chrome-Companion-v1.0.2.zip` separately if you want normal Chrome tab reuse, then follow its README. Existing companion users must update and reload it for minimized-window recovery. Without a connected companion, Setlist shows the search address for manual use.

The companion setup requires explicit local action: per-user native-host registration, Chrome developer-mode loading, and only YouTube host access plus `nativeMessaging`/`storage`. It does not require administrator privileges, a debugging port, firewall changes, or access to other websites. The package creates its connection secret on the destination computer; no installed connection settings or user profiles are distributed.
