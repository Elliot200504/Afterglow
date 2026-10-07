# Small Spotify Web API client
import os
import socket
import threading
import time

import httpx

from . import auth, config

API = "https://api.spotify.com/v1"


class SpotifyError(Exception):
    def __init__(self, kind, message=""):
        super().__init__(message or kind)
        self.kind = kind  # shown as a toast in the UI


class Spotify:
    def __init__(self):
        self.token = config.load_token()
        self.lock = threading.Lock()

    @property
    def linked(self):
        return self.token is not None

    def logout(self):
        self.token = None
        config.delete_token()

    def access_token(self, force=False):
        with self.lock:
            if not self.token:
                raise SpotifyError("not_linked")
            if force or time.time() > self.token["expires_at"] - 60:
                self.token = auth.refresh(self.token)
                if not self.token:
                    config.delete_token()
                    raise SpotifyError("auth", "Login expired, link Spotify again")
                config.save_token(self.token)
            return self.token["access_token"]

    def call(self, method, path, retry=True, **kwargs):
        headers = {"Authorization": "Bearer " + self.access_token()}
        r = httpx.request(method, API + path, headers=headers, timeout=10, **kwargs)

        if r.status_code == 401 and retry:  # token expired early, refresh and try again
            self.access_token(force=True)
            return self.call(method, path, retry=False, **kwargs)
        if r.status_code == 404 and "device" in r.text.lower() and retry and path.startswith("/me/player"):
            self.ensure_device()  # nothing active -> wake up the desktop app and try again
            return self.call(method, path, retry=False, **kwargs)
        if r.status_code == 429:
            raise SpotifyError("rate_limited", "Wait " + r.headers.get("Retry-After", "?") + "s")
        if r.status_code == 403 and "premium" in r.text.lower():
            raise SpotifyError("premium_required")
        if r.status_code >= 400:
            raise SpotifyError("error", f"{r.status_code} {r.text[:100]}")
        if r.content and r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return None

    # --- devices ---
    def my_pc(self):
        devices = self.call("GET", "/me/player/devices")["devices"]
        pcs = [d for d in devices if d["type"] == "Computer"]
        for d in pcs:
            if d["name"].lower() == socket.gethostname().lower():
                return d
        return pcs[0] if pcs else None

    def ensure_device(self):
        pc = self.my_pc()
        if not pc:
            os.startfile("spotify:")  # start the desktop app and wait for it to show up
            for _ in range(20):
                time.sleep(1)
                pc = self.my_pc()
                if pc:
                    break
            else:
                raise SpotifyError("no_device")
        if not pc["is_active"]:
            self.call("PUT", "/me/player", retry=False, json={"device_ids": [pc["id"]]})
            time.sleep(0.5)
        return pc["id"]

    # --- player ---
    def player(self):
        return self.call("GET", "/me/player")

    def play(self, context_uri=None, uris=None, offset=None):
        body = {}
        if context_uri:
            body["context_uri"] = context_uri
        if uris:
            body["uris"] = uris
        if offset:
            body["offset"] = offset
        device = self.ensure_device()
        self.call("PUT", "/me/player/play", params={"device_id": device}, json=body or None)

    def seek(self, ms):
        self.call("PUT", "/me/player/seek", params={"position_ms": int(ms)})

    def volume(self, percent):
        self.call("PUT", "/me/player/volume", params={"volume_percent": int(percent)})

    def shuffle(self, on):
        self.call("PUT", "/me/player/shuffle", params={"state": "true" if on else "false"})

    def repeat(self, mode):
        self.call("PUT", "/me/player/repeat", params={"state": mode})

    def queue(self):
        return self.call("GET", "/me/player/queue")

    def add_to_queue(self, uri):
        self.call("POST", "/me/player/queue", params={"uri": uri})

    # --- liked songs (spotify moved these to /me/library in 2026) ---
    def is_liked(self, uri):
        return self.call("GET", "/me/library/contains", params={"uris": uri})[0]

    def set_liked(self, uri, liked):
        self.call("PUT" if liked else "DELETE", "/me/library", params={"uris": uri})

    # --- browsing ---
    def search(self, q):
        res = self.call("GET", "/search", params={"q": q, "type": "track,album,playlist,artist", "limit": 10})
        return {k: [x for x in res[k]["items"] if x] for k in ("tracks", "albums", "playlists", "artists")}

    def playlists(self):
        lists, url = [], "/me/playlists?limit=50"
        while url:
            page = self.call("GET", url)
            lists += page["items"]
            url = page["next"].replace(API, "") if page["next"] else None
        return lists

    def playlist_tracks(self, playlist_id):
        # only works for your own playlists. "track" was renamed to "item" in 2026
        page = self.call("GET", f"/playlists/{playlist_id}/items", params={"limit": 100})
        return [entry.get("item") or entry.get("track") for entry in page["items"]]
