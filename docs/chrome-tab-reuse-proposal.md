# Normal Chrome tab reuse

Companion 1.0.2 is distributed as a separate manual setup ZIP with Setlist 1.7.22. Installing it requires explicit local approval of YouTube-only host access, nativeMessaging/storage permissions, developer-mode loading, and per-user native-host registration. It is not published in the Chrome Web Store.

## Behavior

The Manifest V3 extension remembers one YouTube tab ID in session storage. Searches call `chrome.tabs.update` for that ID, restore a minimized containing window, and focus its normal Chrome window. On each real input event, Setlist validates the pipe-owning native host and Chrome process ancestry before granting temporary Windows foreground eligibility to that Chrome PID only. Programmatic requests without real foreground input can still be refused by Windows. If there is one existing suitable YouTube tab, it is reused. If several exist, choose one in the companion popup. If none exists, one is created. Closing the chosen tab releases it; moving it between windows retains its identity. Navigating it away from YouTube releases it without changing that page. A committed YouTube page remains eligible while resources are loading; pendingUrl is absent after commit. Unknown URLs, visible navigation outside YouTube, or uncertain results remain guarded. Repeated app clicks retain the newest request during a handoff rather than discarding it. No watch URLs or playback commands are accepted.

The extension requests only `nativeMessaging`, `storage`, and `https://www.youtube.com/*`. It does not request the broad `tabs` permission, other website access, history, cookies, scripting, downloads, screenshots, or debugging. Explicit diagnostic status requests report tab IDs/window IDs/positions without unrelated URLs or titles. Normal operation does not scan other tabs on a timer.

## Local setup

The stable extension ID is `jpiloepffpcgknndlgifihcboiengkcd`. Load the reviewed `chrome-companion/extension` folder through Chrome's Extensions page with developer mode enabled. The companion popup provides Connect and YouTube tab selection. The extension is loaded in the selected normal profile, not incognito.

The packaged helper is `SetlistChromeHost.exe`. Its native host name is `com.openhandgraphics.setlist_youtube`, registered under the per-user Chrome NativeMessagingHosts registry key. Its manifest permits only the exact extension origin. The installed application, helper, config, and extension live below the user's Programs/Setlist directory. The app sends bounded JSON messages through a random named pipe, authenticated with a local random secret. The helper forwards only validated request fields over Chrome's native messaging stdio protocol. There is no new network listener or firewall rule.

The app starts ordinary Chrome if Chrome is closed. When Chrome is already running but the companion is unavailable, it asks the user to connect instead of relaunching Chrome or creating tabs. An uncertain result is never automatically retried. The search address remains available to copy manually.

## Resource and operational limits

The native port keeps Chrome's extension service worker alive. The helper blocks while idle; there are no polling timers or background library scans. This uses some resident memory. Measured native-helper memory excludes Chrome's worker and YouTube page processes. Request latency measurements cover navigation acceptance, not page loading or network time.

Developer-mode loading is local and may show Chrome's normal developer-extension notices. Disabling/removing the extension or changing profiles requires reconnecting the selected profile. Multiple simultaneous YouTube tabs require explicit selection. Live tests preserve the user's other Chrome tabs. Ambiguous, moved and repurposed-tab paths are additionally covered by isolated tests. A complete Chrome restart and cold launch were not live-tested because restarting the user's browser would disturb the existing session.

## Validation and references

Regression tests cover URL restrictions, permission boundaries, request framing/authentication, uncertainty, tab reuse, rapid clicks, moved/closed/repurposed tabs, and choosing among multiple tabs. Packaged tests exercise native messaging and the compact app UI. Live checks verify identical Chrome tab IDs across successive searches, safe closed-tab recovery, unchanged other tab IDs/order, and helper idle resources. No media playback or downloading is part of verification.

Official references: [Chrome Tabs API](https://developer.chrome.com/docs/extensions/reference/api/tabs), [native messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging), and [service-worker lifetime](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle).
