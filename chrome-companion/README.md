# Setlist Chrome companion 1.0.2

This optional connection reuses one YouTube tab in your normal Chrome profile. It selects that tab, restores a minimized window and brings Chrome forward when you click a song in Setlist. It does not play or download music.

## Install or update

1. Install/update Setlist to 1.7.22 first. The app's updater updates the app executable only.
2. Extract the entire companion ZIP to a temporary folder. Review `Install-Companion.ps1` and the extension manifest.
3. Save your work and close Setlist. If the Setlist companion is already loaded, temporarily disable that extension in `chrome://extensions`. Chrome and its other tabs can stay open.
4. Run `Install-Companion.ps1` in PowerShell under your normal script policy. It verifies the package, backs up an existing companion, preserves its connection secret, and registers only this user's native host. `-WhatIf` validates the package and reports the destination without installing. The script does not change execution policy or browser settings.
5. In Chrome Extensions, enable Developer mode and choose **Load unpacked** for `%LOCALAPPDATA%\Programs\Setlist\ChromeBridge\Extension`. If already installed, reload the existing Setlist companion and enable it. Review the YouTube-only access request.
6. Open the companion popup and choose **Connect**, then open Setlist. If several YouTube tabs exist, choose the one to reuse in the companion.

The extension ID stays `jpiloepffpcgknndlgifihcboiengkcd`. Its permissions are `nativeMessaging`, `storage`, and `https://www.youtube.com/*`. No administrator access, debugging port, firewall change or other website access is required. Connection settings and a random secret are created locally; none are included in this package.

Windows may reject requests to focus Chrome when they do not come from a real foreground input event. The application reports connection errors with a search address you can copy. A disabled companion or different Chrome profile must be reconnected. There is no Chrome Web Store listing; developer-mode notices are normal.

## Remove or roll back

Disable/remove this extension in Chrome first and close Setlist. Setup reports the backup folder when updating an existing companion. Restore that folder to `ChromeBridge` and reload the prior extension to roll back. To remove the connection completely, remove only the per-user registry key `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.openhandgraphics.setlist_youtube` and the `Programs\Setlist\ChromeBridge` folder after the native helper exits. Keep Setlist's profile and all music files.

Source: https://github.com/openhandgraphics/setlist-releases/tree/codex/setlist-1.7.22/chrome-companion
