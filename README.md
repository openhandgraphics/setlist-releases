# Setlist for Windows

VirtualDJ playlist studio and app updates. The `website/` folder contains the existing website; `setlist/` contains the desktop source for **1.7.15**.

## Desktop behavior

Describe a playlist or import a song list, review local matches, then explicitly approve adding the playlist to your selected DJ destination. Local playlist matching uses metadata and play counts, not AI or audio similarity. MP3/MP4 recordings are eligible; recognizable karaoke is excluded. Unchecked content preferences are neutral. Unknown content labels and insufficient local matches remain visible.

Artist-style requests are distinct from by-artist requests. Conservative typo handling automatically corrects only confident, unambiguous names. Playlist adjustments preserve selected and favorite songs. Duration requests use an estimated DJ play time of up to 1:45 per song plus 25% spare choices, separately from full-file runtime.

Version 1.7.15 moves the existing approval action beside Close, fixes exclusive navigation highlighting, balances review gutters, and estimates processing time only from credible measurements of current-stage work. Matching animation follows actual result events and never delays completion.

## Develop and test (Windows 10/11, 64-bit)

Requires Python 3.12, Node.js 22, and Microsoft Edge. In PowerShell from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
.\scripts\test.ps1
```

The test script runs 178 Python tests and nine JavaScript regression suites with a temporary isolated app profile and ephemeral port. It does not use your installed Setlist profile. Real music-library fixtures, profiles, credentials, and private verification reports are intentionally absent from this repository.

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

The build uses the Windows .NET Framework compiler and Windows Runtime metadata, then creates `dist/Setlist.exe` with PyInstaller. Compiled binaries are ignored by Git. Building does not install, publish, or replace a running app. Release publication remains a separate explicit action. `setlist-installer/setup.py` is the existing installer implementation retained for regression coverage; creating a new installer release is outside this source update.

Photo OCR runs locally through Windows OCR. Spotify imports and optional catalog discovery retain their existing external-service behavior; no music files are uploaded by playlist matching. Spotify account approval and supported Windows OCR languages are required for those respective features.

## Validation

The local 1.7.15 release passed the automated suites, 15 realistic library requests, compiled UI checks in light/dark and narrow layouts, cancellation, keyboard navigation, restart preservation, and installed-executable smoke verification. No repository CI is currently enabled. `docs/desktop-workflow.example.yml` provides a Windows GitHub Actions template for the same synthetic regression tests and packaging; enabling it requires workflow-write permission. It cannot reproduce private-library or interactive desktop acceptance checks.
