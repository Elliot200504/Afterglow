# Afterglow

A floating retro-neon desktop widget for Windows 11 that shows what the **Spotify desktop app**
is playing and controls it: play/pause, skip, seek, volume, shuffle, repeat and like. You can
also search and pick tracks, albums and playlists, which then play in the Spotify app.

- Now playing comes straight from Windows (media session API): instant and no polling of Spotify.
- Play/pause/next/previous work even without logging in.
- Everything else uses the Spotify Web API (login with PKCE, no client secret).

## Requirements

- Windows 11 (Windows 10 with the WebView2 runtime should also work)
- Python 3.11+
- Spotify desktop app and a **Spotify Premium** account (the Web API player endpoints need Premium)

## One-time setup

1. Go to <https://developer.spotify.com/dashboard> and log in with your normal Spotify account.
2. **Create app**: name it "Afterglow" and tick **Web API**.
3. Add the redirect URI **`http://127.0.0.1:8888/callback`**. It must be the loopback IP;
   Spotify no longer accepts `localhost` redirect URIs.
4. Copy the app's **Client ID** (no secret is needed).
5. Start Afterglow (below). On first launch the widget opens the **LINK SPOTIFY** screen:
   paste the Client ID, click **CONNECT** and approve the login in your browser.

The login is remembered (refresh token in `%APPDATA%\Afterglow\token.json`) and the access token
refreshes silently.

## Running it

### From the source code

Double-click **`run.bat`**. On the first run it creates `.venv` and installs the dependencies.
It starts the widget without a console window.

For development (with a console and log output): `.venv\Scripts\python -m afterglow`.

## Settings

**ALL APP RELATED STUFF IS IN APPDATA/AFTERGLOW**

Settings are in config.json (edit it while Afterglow is closed):

client_id: Your Spotify app's client ID

theme: default or crimson (also set from the tray menu)

hotkey: Show/hide the widget, ctrl+alt+s as standard

always_on_top: Keep the widget above other windows (also set from the tray menu)

scanlines: CRT scanline effect (also set from the tray menu)

x, y, expanded_w, expanded_h: Remembered position and size on the monitor

Want your own colors? All colors live as CSS variables at the top of ui/style.css

Logs: afterglow.log, in the same folder

## Spotify API notes (2026)

- Spotify's February 2026 Web API changes are handled: liking uses `/me/library`, playlist tracks
  use `/playlists/{id}/items`, and search returns at most 10 results per type.
- Spotify only lists the **tracks of playlists you own or collaborate on**. Followed playlists
  still play; they just can't be expanded.
- Development-mode apps require the app owner to have Premium.

## Troubleshooting

| Toast | Meaning |
|---|---|
| SPOTIFY NOT RUNNING | No Spotify desktop device found; start the app (or press Launch Spotify). |
| PREMIUM REQUIRED | The Web API player endpoints need Premium. |
| RATE LIMITED | Spotify asked us to slow down; try again. |
| LOGIN EXPIRED | The refresh token was revoked; link again from the expanded view. |

- Reset everything: quit Afterglow and delete `%APPDATA%\Afterglow`.

## About

Afterglow is a fan project and is not made by, endorsed by or affiliated with Spotify.
Spotify is a trademark of Spotify AB. Afterglow only uses Spotify's public Web API and
the controls Windows already gives every media app.

Afterglow was written with Claude Code, Anthropic's AI coding assistant.

Fonts: Orbitron and Share Tech Mono (SIL Open Font License, see `ui/fonts/`).
