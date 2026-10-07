# The glue between the UI (ui/app.js) and the rest.
# Public methods are callable from javascript as window.pywebview.api.<name>(...).
# Attributes start with _ so pywebview doesn't try to expose them to javascript.
import functools
import json
import os
import socket
import threading
import traceback

import webview

from . import auth, config
from .media import Media
from .spotify import Spotify, SpotifyError


def safe(fn):
    # errors become {"error": kind} so the UI can show a toast instead of crashing.
    # methods that return nothing return True, so the UI can tell "worked" apart from "failed" (null)
    @functools.wraps(fn)
    def wrapper(self, *args):
        try:
            result = fn(self, *args)
            return True if result is None else result
        except SpotifyError as e:
            if e.kind == "auth":
                self._send_auth()
            return {"error": e.kind, "message": str(e)}
        except Exception as e:
            traceback.print_exc()
            return {"error": "error", "message": str(e)}
    return wrapper


class App:
    def __init__(self):
        self._cfg = config.load_config()
        self._window = None
        self._ready = False
        self._expanded = False
        self._grew_up = False
        self._visible = True
        self._media = Media(self._on_media, self._on_art)
        self._spotify = Spotify()
        self._media_state = {"present": False}
        self._art = None
        self._player = None   # last /me/player result (volume, shuffle, ...)
        self._liked = {}      # track uri -> liked?
        self._user_id = None
        self._login_status = ""
        self._wake_poller = threading.Event()

    # ---------- python side ----------
    def _start(self, window):
        self._window = window
        self._media.start()
        threading.Thread(target=self._poll_player, daemon=True).start()

    def _send(self, fn, data):
        if self._ready:
            self._window.run_js(f"afterglow.{fn}({json.dumps(data)})")

    def _save(self, **values):
        self._cfg.update(values)
        config.save_config(self._cfg)

    def _on_media(self, state):
        self._media_state = state
        self._send("onMedia", state)

    def _on_art(self, url):
        self._art = url
        self._send("onArt", url)

    def _send_auth(self):
        self._send("onAuth", self._auth_state())

    def _auth_state(self):
        return {"linked": self._spotify.linked, "client_id": self._cfg["client_id"], "status": self._login_status}

    def _poll_player(self):
        # ask the web api for volume/shuffle/repeat/liked every 5 sec (or right after a command)
        while True:
            if self._spotify.linked:
                try:
                    self._player = self._read_player()
                    self._send("onApi", self._player)
                except Exception as e:
                    print("player poll failed:", e)
                    if not self._spotify.linked:
                        self._send_auth()
            self._wake_poller.wait(5)
            self._wake_poller.clear()

    def _poll_soon(self):
        threading.Timer(0.6, self._wake_poller.set).start()  # spotify needs a moment to update

    def _read_player(self):
        p = self._spotify.player()
        if not p or not p.get("item"):
            return None
        item = p["item"]
        uri = item["uri"]
        if uri not in self._liked and uri.startswith("spotify:track:"):
            self._liked[uri] = self._spotify.is_liked(uri)
        images = item.get("album", {}).get("images") or item.get("images") or []
        return {
            "is_playing": p["is_playing"],
            "progress_ms": p["progress_ms"],
            "shuffle": p["shuffle_state"],
            "repeat": p["repeat_state"],
            "volume": p["device"]["volume_percent"],
            "device_is_local": p["device"]["name"].lower() == socket.gethostname().lower(),
            "liked": self._liked.get(uri, False),
            "item": {
                "uri": uri,
                "name": item["name"],
                "artists": ", ".join(a["name"] for a in item.get("artists", [])),
                "album": item.get("album", {}).get("name"),
                "duration_ms": item["duration_ms"],
                "image": images[0]["url"] if images else None,
            },
        }

    # tray / hotkey stuff
    def _toggle_visible(self):
        self._visible = not self._visible
        if self._visible:
            self._window.show()
        else:
            self._window.hide()

    def _show(self):
        if not self._visible:
            self._toggle_visible()
        self._window.on_top = True  # pops it in front of everything
        self._window.on_top = self._cfg["always_on_top"]

    def _set_option(self, key, value):
        self._save(**{key: value})
        if key == "always_on_top":
            self._window.on_top = value
        self._send("onConfig", self._cfg)

    def _logout(self):
        self._spotify.logout()
        self._player = None
        self._send("onApi", None)
        self._send_auth()

    def _on_moved(self, x, y):
        if self._visible and not (self._expanded and self._grew_up):
            self._save(x=x, y=y)

    # ---------- called from javascript ----------
    def ready(self):
        self._ready = True
        if not self._spotify.linked and not self._cfg["client_id"]:
            self.set_expanded(True)  # first time: show the "link spotify" screen
        return {"config": self._cfg, "auth": self._auth_state(), "media": self._media_state,
                "art": self._art, "api": self._player, "expanded": self._expanded}

    def connect(self, client_id):
        self._save(client_id=client_id)
        self._login_status = "Waiting for login in your browser..."
        self._send_auth()
        threading.Thread(target=self._login, args=(client_id,), daemon=True).start()

    def _login(self, client_id):
        try:
            token = auth.login(client_id)
            config.save_token(token)
            self._spotify.token = token
            self._login_status = "Linked!"
            self._wake_poller.set()
        except Exception as e:
            self._login_status = str(e)
        self._send_auth()

    def _screen(self):
        # the monitor the widget is on
        w = self._window
        return next((s for s in webview.screens if s.x <= w.x < s.x + s.width), webview.screens[0])

    def _fit_on_screen(self, width, height):
        screen = self._screen()
        width = min(max(380, int(width)), screen.width)
        height = min(max(320, int(height)), screen.height - 48)  # 48 = roughly the taskbar
        return width, height

    def set_expanded(self, on):
        self._expanded = on
        w = self._window
        if on:
            width, height = self._fit_on_screen(self._cfg["expanded_w"], self._cfg["expanded_h"])
            # grow upwards if there is no room below (e.g. widget sits above the taskbar)
            screen = self._screen()
            self._grew_up = w.y + height > screen.y + screen.height - 48
            w.resize(width, height)
            if self._grew_up:
                w.move(w.x, max(screen.y, w.y + config.COMPACT[1] - height))
        else:
            if self._grew_up:
                w.move(w.x, w.y + w.height - config.COMPACT[1])
            w.resize(*config.COMPACT)

    def resize(self, width, height):
        width, height = self._fit_on_screen(width, height)
        self._window.resize(width, height)
        self._save(expanded_w=width, expanded_h=height)

    @safe
    def toggle_play(self):
        if not self._media.toggle():
            if not self._spotify.linked:
                raise SpotifyError("no_device")
            self._spotify.play()  # spotify app not running -> start it through the web api

    @safe
    def next_track(self):
        self._media.next()

    @safe
    def prev_track(self):
        self._media.previous()

    @safe
    def seek(self, ms):
        if self._spotify.linked:
            self._spotify.seek(ms)
        else:
            self._media.seek(ms)

    @safe
    def set_volume(self, percent):
        self._spotify.volume(percent)
        self._poll_soon()

    @safe
    def set_shuffle(self, on):
        self._spotify.shuffle(on)
        self._poll_soon()

    @safe
    def set_repeat(self, mode):
        self._spotify.repeat(mode)
        self._poll_soon()

    @safe
    def toggle_like(self):
        uri = self._player["item"]["uri"]
        liked = not self._spotify.is_liked(uri)
        self._spotify.set_liked(uri, liked)
        self._liked[uri] = liked
        return liked

    @safe
    def launch_spotify(self):
        if self._spotify.linked:
            self._spotify.play()  # starts the app, moves playback here and resumes
        else:
            os.startfile("spotify:")

    @safe
    def search(self, q):
        return self._spotify.search(q)

    @safe
    def playlists(self):
        if not self._user_id:
            self._user_id = self._spotify.call("GET", "/me")["id"]
        result = []
        for p in self._spotify.playlists():
            result.append({
                "id": p["id"], "uri": p["uri"], "name": p["name"], "images": p["images"], "owner": p["owner"],
                "total": (p.get("items") or p.get("tracks") or {}).get("total"),
                "own": p["owner"]["id"] == self._user_id or p["collaborative"],  # can only list tracks of these
            })
        return result

    @safe
    def playlist_tracks(self, playlist_id):
        return self._spotify.playlist_tracks(playlist_id)

    @safe
    def queue(self):
        return self._spotify.queue()

    @safe
    def play(self, opts):
        self._spotify.play(opts.get("context_uri"), opts.get("uris"), opts.get("offset"))
        self._poll_soon()

    @safe
    def add_to_queue(self, uri):
        self._spotify.add_to_queue(uri)
