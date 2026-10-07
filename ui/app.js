// Afterglow UI
// Python sends us updates by calling afterglow.onMedia(...), afterglow.onApi(...) etc (see the bottom part).
// We call Python with call('method_name', args), which runs the method with that name in afterglow/app.py.

const $ = (id) => document.getElementById(id);
const card = $('card');

let media = null;       // what windows says is playing (title, artist, position...)
let player = null;      // extra info from the spotify web api (volume, shuffle, repeat, liked...)
let auth = { linked: false };
let coverFromWindows = null;
let currentTrack = null;
let expanded = false;
let currentTab = 'search';

// ---------- talking to python ----------

const ERRORS = {
  no_device: 'SPOTIFY NOT RUNNING',
  premium_required: 'PREMIUM REQUIRED',
  rate_limited: 'RATE LIMITED',
  not_linked: 'LINK SPOTIFY FIRST',
  auth: 'LOGIN EXPIRED, LINK AGAIN',
};

// Calls a python method. If python returns {error: ...} we show it as a toast and return null.
async function call(name, ...args) {
  const result = await window.pywebview.api[name](...args);
  if (result && result.error) {
    toast(ERRORS[result.error] || result.message.toUpperCase().slice(0, 50), true);
    if (result.error === 'not_linked') openSetup();
    return null;
  }
  return result;
}

function toast(text, isError = false) {
  const t = $('toast');
  t.textContent = text;
  t.classList.toggle('error', isError);
  t.classList.add('show');
  clearTimeout(t.timer);
  t.timer = setTimeout(() => t.classList.remove('show'), 2600);
}

// 215000 -> "3:35"
function formatTime(ms) {
  const sec = Math.max(0, Math.floor(ms / 1000));
  return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0');
}

// ---------- progress bar ----------
// Python only tells us the position every half second, so in between we move the bar ourselves.

let position = 0;          // ms at the moment we last synced
let syncedAt = 0;          // performance.now() when we synced
let duration = 0;
let playing = false;
let draggingBar = false;
let ignoreUpdatesUntil = 0; // after seeking, spotify needs a moment before it reports the new position

function nowPosition() {
  const p = position + (playing ? performance.now() - syncedAt : 0);
  return Math.min(p, duration || p);
}

function syncPosition(ms, isPlaying, force) {
  if (!force && performance.now() < ignoreUpdatesUntil) return;
  if (force || isPlaying !== playing || Math.abs(nowPosition() - ms) > 1500) {
    position = ms;
    syncedAt = performance.now();
  }
  playing = isPlaying;
}

function drawBar(ms) {
  const percent = duration ? (ms / duration) * 100 : 0;
  $('bar-fill').style.width = percent + '%';
  $('playhead').style.left = percent + '%';
  $('t-elapsed').textContent = formatTime(ms);
  $('t-total').textContent = formatTime(duration);
}

function animate() {
  if (!draggingBar) drawBar(nowPosition());
  requestAnimationFrame(animate);
}
requestAnimationFrame(animate);

// ---------- now playing ----------

// Windows' info is the main source. If windows has nothing but spotify plays on this pc, use the web api's.
function getTrack() {
  if (media && media.present && media.title) {
    return { id: media.track_key, title: media.title, artist: media.artist, album: media.album,
             playing: media.status === 'playing', position: media.position_ms, duration: media.duration_ms };
  }
  if (player && player.device_is_local) {
    const item = player.item;
    return { id: item.uri, title: item.name, artist: item.artists, album: item.album,
             playing: player.is_playing, position: player.progress_ms, duration: item.duration_ms };
  }
  return null;
}

function render() {
  const track = getTrack();
  card.classList.toggle('no-signal', !track);
  card.classList.toggle('has-track', !!track);
  card.classList.toggle('no-api', !auth.linked);

  if (!track) {
    card.classList.add('paused');
    setTitle('NO SIGNAL');
    $('artist').textContent = '';
    $('album').textContent = '';
    currentTrack = null;
    duration = 0;
    syncPosition(0, false, true);
    showCover(null);
    return;
  }

  if (track.id !== currentTrack) {
    if (currentTrack) glitch();  // not on the very first track
    currentTrack = track.id;
    setTitle(track.title);
    $('artist').textContent = track.artist;
    $('album').textContent = track.album;
    duration = track.duration;
    syncPosition(track.position, track.playing, true);
  } else {
    syncPosition(track.position, track.playing, false);
  }

  card.classList.toggle('paused', !track.playing);
  $('play-icon').setAttribute('href', track.playing ? '#i-pause' : '#i-play');

  // does the web api info belong to the same song? (it updates slower than windows)
  const sameSong = player && player.item.name.toLowerCase() === track.title.toLowerCase();
  showCover(coverFromWindows || (sameSong ? player.item.image : null));

  if (player) {
    $('btn-shuffle').classList.toggle('on', player.shuffle);
    $('btn-repeat').classList.toggle('on', player.repeat !== 'off');
    $('btn-repeat').classList.toggle('track', player.repeat === 'track');
    $('btn-like').classList.toggle('on', sameSong && player.liked);
    if (!changingVolume) setVolumeSlider(player.volume);
  }
}

// long titles scroll back and forth, short ones stand still
function setTitle(text) {
  const box = $('title-box');
  const title = $('title');
  title.textContent = text;
  box.classList.remove('scroll');
  requestAnimationFrame(() => {
    const overflow = title.scrollWidth - box.clientWidth;
    if (overflow > 4) {
      box.style.setProperty('--dist', overflow + 12 + 'px');
      box.style.setProperty('--dur', Math.max(5, overflow / 22) + 's');
      box.classList.add('scroll');
    }
  });
}

function glitch() {
  $('title').classList.add('glitch');
  card.classList.add('flicker');
  setTimeout(() => {
    $('title').classList.remove('glitch');
    card.classList.remove('flicker');
  }, 520);
}

// two <img> on top of each other so the new cover can fade in over the old one
let shownCover = null;
let frontImg = $('art-a');
let backImg = $('art-b');

function showCover(src) {
  if (src === shownCover) return;
  shownCover = src;
  const wrap = card.querySelector('.art-wrap');
  if (!src) {
    frontImg.classList.remove('show');
    wrap.classList.remove('has-art');
    return;
  }
  backImg.onload = () => {
    backImg.classList.add('show');
    frontImg.classList.remove('show');
    wrap.classList.add('has-art');
    [frontImg, backImg] = [backImg, frontImg];
  };
  backImg.src = src;
}

// ---------- buttons ----------

// the whole card drags the window (pywebview-drag-region), except buttons and sliders
card.addEventListener('mousedown', (e) => {
  if (e.target.closest('button, input, .bar, .vol-pop')) e.stopPropagation();
});

$('btn-play').onclick = () => call('toggle_play');
$('btn-next').onclick = () => call('next_track');
$('btn-prev').onclick = () => call('prev_track');

$('btn-launch').onclick = async () => {
  $('btn-launch').textContent = 'LAUNCHING...';
  await call('launch_spotify');
  $('btn-launch').textContent = 'LAUNCH SPOTIFY';
};

$('btn-shuffle').onclick = async () => {
  const on = !(player && player.shuffle);
  if (await call('set_shuffle', on) !== null && player) player.shuffle = on;
  render();
};

$('btn-repeat').onclick = async () => {
  // off -> context (whole album/playlist) -> track -> off
  const next = { off: 'context', context: 'track', track: 'off' }[player ? player.repeat : 'off'];
  if (await call('set_repeat', next) !== null && player) player.repeat = next;
  render();
};

$('btn-like').onclick = async () => {
  const liked = await call('toggle_like');
  if (liked === null) return;
  player.liked = liked;
  render();
  toast(liked ? 'SAVED TO LIKED SONGS' : 'REMOVED FROM LIKED SONGS');
};

// volume: wait until the slider stops moving before telling spotify
let changingVolume = false;
let volumeTimer = null;

function setVolumeSlider(v) {
  $('vol').value = v;
  $('vol').style.setProperty('--pct', v + '%');
  $('vol-val').textContent = v;
}

$('vol').oninput = () => {
  const v = Number($('vol').value);
  setVolumeSlider(v);
  changingVolume = true;
  clearTimeout(volumeTimer);
  volumeTimer = setTimeout(async () => {
    await call('set_volume', v);
    setTimeout(() => (changingVolume = false), 3000);
  }, 200);
};

// seeking: click or drag on the progress bar
const bar = $('bar');

function barToMs(e) {
  const rect = bar.getBoundingClientRect();
  const fraction = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
  return Math.round(fraction * duration);
}

bar.onmousedown = (e) => {
  if (!duration) return;
  draggingBar = true;
  drawBar(barToMs(e));
  const move = (ev) => drawBar(barToMs(ev));
  const release = (ev) => {
    window.removeEventListener('mousemove', move);
    window.removeEventListener('mouseup', release);
    draggingBar = false;
    position = barToMs(ev);
    syncedAt = performance.now();
    ignoreUpdatesUntil = performance.now() + 2500;
    call('seek', position);
  };
  window.addEventListener('mousemove', move);
  window.addEventListener('mouseup', release);
};

// ---------- expanded mode ----------

$('btn-expand').onclick = () => setExpanded(!expanded);

function setExpanded(on, tellPython = true) {
  expanded = on;
  $('app').classList.toggle('expanded', on);
  if (tellPython) call('set_expanded', on);
  if (on) showTab(auth.linked ? currentTab : 'setup');
}

document.querySelectorAll('.tab').forEach((tab) => {
  tab.onclick = () => showTab(tab.dataset.tab);
});

function showTab(name) {
  if (name !== 'setup') currentTab = name;
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === name));
  for (const tab of ['search', 'playlists', 'queue', 'setup']) {
    $('tab-' + tab).hidden = tab !== name;
  }
  if (name === 'setup') return;
  if (!auth.linked) {
    showMessage(listFor(name), 'Link your Spotify account first.');
    return;
  }
  if (name === 'search') $('search-input').focus();
  if (name === 'playlists') loadPlaylists();
  if (name === 'queue') loadQueue();
}

function listFor(tab) {
  return $({ search: 'search-results', playlists: 'playlist-list', queue: 'queue-list' }[tab]);
}

function openSetup() {
  if (!expanded) setExpanded(true);
  showTab('setup');
}

// resize by dragging the corner in the bottom right
const grip = document.querySelector('.grip');
grip.onpointerdown = (e) => {
  grip.setPointerCapture(e.pointerId);  // keep getting mouse events even if the mouse leaves the window
  const startX = e.screenX, startY = e.screenY;
  const startW = window.innerWidth, startH = window.innerHeight;
  let busy = false;
  grip.onpointermove = async (ev) => {
    if (busy) return;  // skip moves while python is still resizing
    busy = true;
    await window.pywebview.api.resize(startW + ev.screenX - startX, startH + ev.screenY - startY);
    busy = false;
  };
  grip.onpointerup = () => (grip.onpointermove = null);
};

// ---------- link spotify ----------

function renderAuth() {
  if (auth.client_id && !$('client-id').value) $('client-id').value = auth.client_id;
  $('setup-status').textContent = auth.status || 'Play/pause/skip already work without linking.';
  $('btn-connect').textContent = auth.linked ? 'RELINK' : 'CONNECT';
  if (auth.linked && auth.status === 'Linked!' && !$('tab-setup').hidden) showTab('search');
}

$('btn-connect').onclick = () => {
  const id = $('client-id').value.trim();
  if (id.length !== 32) {
    toast('THE CLIENT ID IS 32 CHARACTERS', true);
    return;
  }
  call('connect', id);
};

// ---------- lists (search results, playlists, queue) ----------

function showMessage(list, text) {
  list.innerHTML = '';
  const div = document.createElement('div');
  div.className = 'hint';
  div.textContent = text;
  list.append(div);
}

function addLabel(list, text) {
  const div = document.createElement('div');
  div.className = 'section-label';
  div.textContent = text;
  list.append(div);
}

// smallest picture that is still at least 64px
function smallImage(images) {
  if (!images || !images.length) return null;
  const sorted = [...images].sort((a, b) => (a.width || 0) - (b.width || 0));
  return (sorted.find((img) => img.width >= 64) || sorted[sorted.length - 1]).url;
}

function artistNames(artists) {
  return (artists || []).map((a) => a.name).join(', ');
}

// one clickable line in a list. right click (or the + button) adds a track to the queue
function addRow(list, { image, number, name, sub, onClick, onQueue, round }) {
  const row = document.createElement('div');
  row.className = 'row' + (round ? ' artist-row' : '');
  let html = '';
  if (number !== undefined) html += `<span class="num">${number}</span>`;
  if (image !== undefined) html += image ? `<img src="${image}" loading="lazy">` : '<div class="noimg"></div>';
  html += '<div class="row-text"><div class="row-name"></div><div class="row-sub"></div></div>';
  row.innerHTML = html;
  row.querySelector('.row-name').textContent = name;   // textContent so weird song names can't break the html
  row.querySelector('.row-sub').textContent = sub || '';
  if (onClick) row.onclick = onClick;
  if (onQueue) {
    const plus = document.createElement('button');
    plus.className = 'btn';
    plus.title = 'Add to queue';
    plus.innerHTML = '<svg><use href="#i-plus"/></svg>';
    plus.onclick = (e) => { e.stopPropagation(); onQueue(); };
    row.append(plus);
    row.oncontextmenu = (e) => { e.preventDefault(); onQueue(); };
  }
  list.append(row);
  return row;
}

async function play(what, name) {
  if (await call('play', what) !== null) toast('PLAYING ' + name);
}

async function addToQueue(uri, name) {
  if (await call('add_to_queue', uri) !== null) toast('QUEUED ' + name);
}

// search (waits until you stop typing for 300ms)
let searchTimer = null;
$('search-input').oninput = () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(search, 300);
};

async function search() {
  const query = $('search-input').value.trim();
  const list = $('search-results');
  if (!query) {
    showMessage(list, 'type to search · right-click a track to queue it');
    return;
  }
  const results = await call('search', query);
  if (!results || query !== $('search-input').value.trim()) return;  // you typed more in the meantime
  list.innerHTML = '';

  if (results.tracks.length) addLabel(list, 'TRACKS');
  for (const t of results.tracks) {
    addRow(list, {
      image: smallImage(t.album.images), name: t.name, sub: artistNames(t.artists) + ' · ' + formatTime(t.duration_ms),
      onClick: () => play({ context_uri: t.album.uri, offset: { uri: t.uri } }, t.name),  // keeps playing the album after
      onQueue: () => addToQueue(t.uri, t.name),
    });
  }
  if (results.albums.length) addLabel(list, 'ALBUMS');
  for (const a of results.albums) {
    addRow(list, { image: smallImage(a.images), name: a.name, sub: artistNames(a.artists),
                   onClick: () => play({ context_uri: a.uri }, a.name) });
  }
  if (results.playlists.length) addLabel(list, 'PLAYLISTS');
  for (const p of results.playlists) {
    addRow(list, { image: smallImage(p.images), name: p.name, sub: 'by ' + p.owner.display_name,
                   onClick: () => play({ context_uri: p.uri }, p.name) });
  }
  if (results.artists.length) addLabel(list, 'ARTISTS');
  for (const a of results.artists) {
    addRow(list, { image: smallImage(a.images), name: a.name, sub: 'artist', round: true,
                   onClick: () => play({ context_uri: a.uri }, a.name) });
  }
  if (!list.children.length) showMessage(list, 'no results');
}

// playlists. the arrow shows the songs, but spotify only allows that for your own playlists
async function loadPlaylists() {
  const list = $('playlist-list');
  if (list.dataset.loaded) return;
  showMessage(list, 'loading...');
  const playlists = await call('playlists');
  if (!playlists) return;
  list.dataset.loaded = 'yes';
  list.innerHTML = '';

  for (const p of playlists) {
    const sub = (p.total != null ? p.total + ' tracks · ' : '') + (p.own ? '' : 'followed · ') + p.owner.display_name;
    const row = addRow(list, { image: smallImage(p.images), name: p.name, sub, onClick: () => play({ context_uri: p.uri }, p.name) });
    if (!p.own) continue;

    const songs = document.createElement('div');
    songs.className = 'subtracks';
    songs.hidden = true;
    list.append(songs);

    const arrow = document.createElement('button');
    arrow.className = 'btn caret';
    arrow.title = 'Show songs';
    arrow.innerHTML = '<svg><use href="#i-chevron"/></svg>';
    row.append(arrow);
    arrow.onclick = async (e) => {
      e.stopPropagation();
      songs.hidden = !songs.hidden;
      row.classList.toggle('open', !songs.hidden);
      if (songs.hidden || songs.children.length) return;
      const tracks = await call('playlist_tracks', p.id);
      (tracks || []).forEach((t, i) => {
        if (!t) return;
        addRow(songs, { number: i + 1, name: t.name, sub: artistNames(t.artists),
                        onClick: () => play({ context_uri: p.uri, offset: { position: i } }, t.name),
                        onQueue: () => addToQueue(t.uri, t.name) });
      });
    };
  }
}

async function loadQueue() {
  const list = $('queue-list');
  const q = await call('queue');
  if (!q) return;
  list.innerHTML = '';
  if (q.currently_playing) {
    addLabel(list, 'NOW PLAYING');
    const t = q.currently_playing;
    addRow(list, { image: smallImage((t.album || t).images), name: t.name, sub: artistNames(t.artists) })
      .classList.add('current');
  }
  if (q.queue.length) addLabel(list, 'NEXT UP');
  q.queue.forEach((t, i) => {
    addRow(list, { number: i + 1, image: smallImage((t.album || t).images), name: t.name, sub: artistNames(t.artists) });
  });
  if (!list.children.length) showMessage(list, 'queue is empty');
}

// ---------- updates from python ----------

function applyConfig(cfg) {
  document.documentElement.dataset.theme = cfg.theme;
  document.documentElement.classList.toggle('scanlines', cfg.scanlines);
}

window.afterglow = {
  onMedia(state) {
    media = state;
    if (!state.present) coverFromWindows = null;
    render();
  },
  onArt(url) {
    coverFromWindows = url;
    render();
  },
  onApi(state) {
    player = state;
    render();
  },
  onAuth(state) {
    auth = state;
    render();
    renderAuth();
  },
  onConfig: applyConfig,
};

// no right click menu (it would show "reload" etc)
document.oncontextmenu = (e) => {
  if (e.target.tagName !== 'INPUT') e.preventDefault();
};

// ---------- start ----------

async function start() {
  const info = await call('ready');
  applyConfig(info.config);
  auth = info.auth;
  media = info.media;
  player = info.api;
  coverFromWindows = info.art;
  render();
  renderAuth();
  if (info.expanded) setExpanded(true, false);
}

// pywebview needs a moment before window.pywebview.api exists
if (window.pywebview) start();
else window.addEventListener('pywebviewready', start);
