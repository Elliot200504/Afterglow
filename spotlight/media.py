# Reads what the Spotify desktop app is playing through Windows' media controls (GSMTC)
# and can play/pause/skip it. Works without logging in to Spotify.
import asyncio
import base64
import datetime
import io
import threading

from PIL import Image
from winrt.windows.media.control import GlobalSystemMediaTransportControlsSessionManager as Manager
from winrt.windows.storage.streams import Buffer, InputStreamOptions

PLAYING, PAUSED = 4, 5


class Media:
    def __init__(self, on_update, on_art):
        self.on_update = on_update  # called with a dict every poll
        self.on_art = on_art        # called with a data: url when the cover changes
        self.loop = None
        self.manager = None
        self.track = None
        self.art = None
        self.art_checks = 0

    def start(self):
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self.loop.run_until_complete, args=(self.run(),), daemon=True).start()

    async def run(self):
        self.manager = await Manager.request_async()
        while True:
            try:
                await self.poll()
            except Exception as e:
                print("media poll failed:", e)
            await asyncio.sleep(0.5)

    def session(self):
        # only the spotify app, so youtube in the browser etc is ignored
        for s in self.manager.get_sessions():
            if "spotify" in s.source_app_user_model_id.lower():
                return s

    async def poll(self):
        s = self.session()
        if not s:
            self.track = self.art = None
            self.on_update({"present": False})
            return

        props = await s.try_get_media_properties_async()
        status = s.get_playback_info().playback_status
        tl = s.get_timeline_properties()

        position = tl.position.total_seconds() * 1000
        if status == PLAYING:  # spotify only updates the position now and then, so add the time since
            position += (datetime.datetime.now(datetime.timezone.utc) - tl.last_updated_time).total_seconds() * 1000

        track = f"{props.title}|{props.artist}|{props.album_title}"
        if track != self.track:
            self.track = track
            self.art_checks = 4  # the cover sometimes arrives a bit after the title, check a few times
        if self.art_checks > 0 and props.thumbnail:
            self.art_checks -= 1
            await self.read_art(props.thumbnail)

        self.on_update({
            "present": True,
            "status": "playing" if status == PLAYING else "paused",
            "title": props.title,
            "artist": props.artist,
            "album": props.album_title,
            "position_ms": int(position),
            "duration_ms": int(tl.end_time.total_seconds() * 1000),
            "track_key": track,
        })

    async def read_art(self, thumbnail):
        stream = await thumbnail.open_read_async()
        buf = Buffer(stream.size)
        data = bytes(await stream.read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD))
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((240, 240))  # spotify gives a big png, shrink it before sending it to the ui
        out = io.BytesIO()
        img.save(out, "JPEG", quality=88)
        url = "data:image/jpeg;base64," + base64.b64encode(out.getvalue()).decode()
        if url != self.art:
            self.art = url
            self.on_art(url)

    # --- controls (called from other threads) ---
    def command(self, name, *args):
        async def run():
            s = self.session()
            return bool(s and await getattr(s, name)(*args))
        return asyncio.run_coroutine_threadsafe(run(), self.loop).result(timeout=3)

    def toggle(self):
        return self.command("try_toggle_play_pause_async")

    def next(self):
        return self.command("try_skip_next_async")

    def previous(self):
        return self.command("try_skip_previous_async")

    def seek(self, ms):
        return self.command("try_change_playback_position_async", int(ms * 10_000))
