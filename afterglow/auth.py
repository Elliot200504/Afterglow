# Spotify login with PKCE (no client secret needed)
import base64
import hashlib
import http.server
import secrets
import time
import urllib.parse
import webbrowser

import httpx

TOKEN_URL = "https://accounts.spotify.com/api/token"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = ("user-read-playback-state user-modify-playback-state user-read-currently-playing "
          "playlist-read-private playlist-read-collaborative user-library-read user-library-modify")


def login(client_id):
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            if query.get("state") == state:
                result.update(query)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h1 style='font-family:sans-serif'>Afterglow is linked, you can close this tab.</h1>")

        def log_message(self, *args):
            pass

    params = urllib.parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "code_challenge_method": "S256",
        "code_challenge": challenge,
        "scope": SCOPES,
        "state": state,
    })
    # start listening first, then open the browser and wait for spotify to redirect back (max 5 min)
    with http.server.HTTPServer(("127.0.0.1", 8888), Handler) as server:
        webbrowser.open("https://accounts.spotify.com/authorize?" + params)
        server.timeout = 5
        give_up = time.time() + 300
        while "code" not in result and "error" not in result and time.time() < give_up:
            server.handle_request()

    if "code" not in result:
        raise Exception("Login failed: " + result.get("error", "no response"))

    r = httpx.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "code": result["code"],
        "redirect_uri": REDIRECT_URI,
        "client_id": client_id,
        "code_verifier": verifier,
    })
    r.raise_for_status()
    token = r.json()
    token["client_id"] = client_id
    token["expires_at"] = time.time() + token["expires_in"]
    return token


def refresh(token):
    r = httpx.post(TOKEN_URL, data={
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
        "client_id": token["client_id"],
    })
    if r.status_code == 400:
        return None  # refresh token revoked -> need to log in again
    r.raise_for_status()
    new = {**token, **r.json()}  # spotify sometimes sends a new refresh token
    new["expires_at"] = time.time() + new["expires_in"]
    return new
