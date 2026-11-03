#!/usr/bin/env python3
"""
Spotify LAN Music Player — single-file version.

Put this ONE file in your music folder and run:

    python Spotify.py

Then open the printed LAN address from another device.

Music is scanned recursively from this script's folder.

Supported audio:
    MP3, FLAC, WAV, M4A, AAC, OGG, OPUS, WEBM

Artwork:
    1. Embedded album artwork (when Mutagen is installed)
    2. cover.jpg / cover.jpeg / cover.png / cover.webp in the song's folder
    3. album.jpg / album.jpeg / album.png / album.webp in the song's folder
    4. <song-name>.jpg/png/webp next to the song
    5. Spotify-style music-note fallback

Optional artwork metadata support:
    pip install mutagen

Lyrics:
    Fetched from LRCLIB (free) and saved next to each song as
    <song>.lyrics.json so they work offline after the first fetch.
    On startup the server downloads any missing lyrics in the background.

The player itself is embedded below — there is no separate HTML file.
"""

from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import quote, unquote, urlparse
import base64
import io
import json
import mimetypes
import os
import re
import socket
import tempfile
import urllib.request
import urllib.parse
import urllib.error

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get("PULSE_PORT", "8000"))

AUDIO_EXTS = {
    ".mp3", ".flac", ".wav", ".m4a", ".aac",
    ".ogg", ".opus", ".webm", ".oga"
}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
IGNORED_DIRS = {".git", "__pycache__", "node_modules"}

PLAYER_HTML = '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>Spotify — Music Player</title>\n<style>\n:root{\n  --bg:#000;--panel:#121212;--panel2:#181818;--panel3:#242424;--text:#fff;\n  --muted:#a7a7a7;--green:#1ed760;--hover:#2a2a2a;--line:#303030;\n}\n*{box-sizing:border-box}\nhtml,body{margin:0;height:100%;background:#000;color:var(--text);font-family:Arial,Helvetica,sans-serif;overflow:hidden}\nbutton,input{font:inherit}\nbutton{border:0;color:inherit;background:none;cursor:pointer}\n.app{height:100vh;display:grid;grid-template-columns:300px 1fr;grid-template-rows:1fr 90px;gap:8px;padding:8px;background:#000}\n.sidebar,.main,.nowpanel,.player{background:var(--panel);border-radius:8px}\n.sidebar{grid-row:1;display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden;border:1px solid #202020}\n.nav{padding:12px 10px 8px;flex:none}\n.nav button{width:100%;display:flex;align-items:center;gap:14px;padding:11px 13px;border-radius:7px;color:#b3b3b3;font-weight:700;text-align:left;white-space:nowrap;overflow:hidden}\n.nav button:hover,.nav button.active{color:#fff;background:linear-gradient(90deg,var(--green-dark),#1d1d1d)}\n.icon{width:22px;text-align:center;font-size:19px}\n.library-head{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 14px 7px;font-weight:700;min-width:0;flex:none}.library-head>span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n.library-head .actions{display:flex;gap:4px;flex:none}\n.circle-btn{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;flex:none}\n.circle-btn:hover{background:#2a2a2a}\n.filters{display:flex;gap:7px;overflow-x:auto;overflow-y:hidden;padding:4px 14px 9px;scrollbar-width:none;flex:none}.filters::-webkit-scrollbar{display:none}\n.chip{background:#2a2a2a;padding:7px 12px;border-radius:999px;font-size:12px;white-space:nowrap}\n.chip.active{background:#fff;color:#000}\n.library-search{margin:0 10px 8px;position:relative;flex:none}\n.library-search input{width:100%;border:0;border-radius:5px;background:#242424;color:#fff;padding:9px 10px 9px 32px;outline:none}\n.library-search span{position:absolute;left:10px;top:8px;color:#aaa}\n.library-list{overflow-x:hidden;overflow-y:auto;padding:2px 8px 12px;min-height:0;flex:1}\n.lib-item{display:flex;gap:10px;align-items:center;padding:7px;border-radius:6px;min-width:0}\n.lib-item:hover{background:linear-gradient(90deg,#183822,#1f1f1f)}\n.cover-sm{width:48px;height:48px;border-radius:4px;object-fit:cover;background:linear-gradient(135deg,#333,#111);flex:none}\n.lib-text{min-width:0;flex:1;overflow:hidden}\n.lib-title{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}\n.lib-sub{font-size:11px;color:#999;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.main{min-width:0;overflow:hidden;position:relative}\n.topbar{height:68px;display:flex;align-items:center;gap:12px;padding:12px 18px;background:linear-gradient(90deg,#121212 0%,#151b16 100%);position:sticky;top:0;z-index:4}\n.nav-arrows{display:flex;gap:8px}\n.top-round{width:34px;height:34px;border-radius:50%;background:#080808;color:#aaa;font-size:19px}\n.top-round:hover{color:#fff;background:#242424}\n.search{height:40px;max-width:520px;flex:1;background:#242424;border-radius:22px;display:flex;align-items:center;padding:0 16px;gap:9px}\n.search input{width:100%;background:none;border:0;outline:0;color:#fff;font-size:14px}.search:focus-within{box-shadow:0 0 0 2px var(--green)}\n.content{height:calc(100% - 68px);overflow:auto;padding:0 24px 120px}\n.hero{padding:24px 0 18px}\n.hero h1{font-size:29px;margin:0 0 18px}\n.quick-grid{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:9px}\n.quick{display:flex;align-items:center;background:#292929;border-radius:5px;overflow:hidden;height:64px;transition:.15s}\n.quick:hover{background:#3a3a3a}\n.quick img{width:64px;height:64px;object-fit:cover}\n.quick span{padding:0 12px;font-weight:700;font-size:13px}\n.section{margin-top:26px}\n.section-head{display:flex;justify-content:space-between;align-items:end;margin-bottom:12px}\n.section h2{font-size:21px;margin:0}\n.showall{color:#aaa;font-size:12px;font-weight:700}\n.showall:hover{color:#fff;text-decoration:underline}\n.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:18px}\n.card{min-width:0;padding:12px;border-radius:6px;background:#181818;transition:.15s}\n.card:hover{background:#242424}\n.card img{width:100%;aspect-ratio:1;border-radius:5px;object-fit:cover;background:#222}\n.card-title{font-size:14px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:10px}\n.card-sub{font-size:12px;color:#a7a7a7;margin-top:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.track-table{width:100%;border-collapse:collapse;margin-top:8px}\n.track-table th{text-align:left;color:#999;font-size:11px;text-transform:uppercase;font-weight:400;padding:8px 10px;border-bottom:1px solid #2b2b2b}\n.track-table td{padding:8px 10px;color:#ddd;font-size:13px}\n.track-row{border-radius:5px}\n.track-row:hover{background:#252525}\n.track-row.playing td{color:var(--green)}.track-row.playing{background:#102719}\n.track-main{display:flex;align-items:center;gap:10px}\n.track-art{width:40px;height:40px;border-radius:3px;object-fit:cover}\n.like{font-size:18px;color:#aaa}.like.liked{color:var(--green)}\n.nowpanel{position:absolute;right:8px;top:76px;bottom:8px;width:330px;z-index:5;padding:16px;display:none;overflow:auto;background:#181818;box-shadow:-12px 0 30px #0008}\n.nowpanel.open{display:block}\n.now-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:15px;font-weight:700}\n.now-cover{width:100%;aspect-ratio:1;object-fit:cover;border-radius:5px}\n.now-title{font-size:22px;font-weight:700;margin-top:16px}\n.now-artist{color:#aaa;margin-top:6px}\n.now-section{background:#242424;border-radius:7px;margin-top:18px;padding:14px}\n.now-section h3{font-size:14px;margin:0 0 8px}.now-section p{font-size:12px;color:#aaa;line-height:1.5;margin:0}\n.player{grid-column:1 / -1;display:grid;border-top:1px solid #202020;grid-template-columns:300px 1fr 300px;align-items:center;padding:8px 14px;position:relative;z-index:20}\n.current{display:flex;align-items:center;gap:10px;min-width:0}\n.current img{width:58px;height:58px;object-fit:cover;border-radius:4px}\n.current-info{min-width:0}.current-title{font-size:13px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.current-artist{font-size:11px;color:#aaa;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.player-center{display:flex;flex-direction:column;align-items:center;gap:5px}\n.controls{display:flex;align-items:center;gap:17px}.controls button{color:#aaa;font-size:16px}.controls button:hover{color:#fff}\n.play{width:36px;height:36px;border-radius:50%;background:var(--green);color:#000!important;display:grid;place-items:center;font-size:15px!important;box-shadow:0 0 0 3px #1ed76018}.play:hover{transform:scale(1.04);background:#35e878}\n.progress{width:min(650px,90%);display:flex;align-items:center;gap:7px;color:#999;font-size:9px}\n.range{appearance:none;height:4px;border-radius:99px;background:#555;outline:none;flex:1}\n.range::-webkit-slider-thumb{appearance:none;width:11px;height:11px;border-radius:50%;background:#fff}\n.range:hover::-webkit-slider-thumb{background:var(--green)}\n.player-right{display:flex;justify-content:flex-end;align-items:center;gap:12px;color:#aaa}\n.player-right button:hover{color:#fff}\n.volume{width:100px}\n.drop{position:absolute;inset:0;background:#000c;display:none;align-items:center;justify-content:center;z-index:50;border:2px dashed var(--green);font-size:25px;font-weight:700}\n.drop.show{display:flex}\n.empty{padding:40px;text-align:center;color:#888}\n@media(max-width:1000px){\n .app{grid-template-columns:220px 1fr}.player{grid-template-columns:220px 1fr 180px}.quick-grid{grid-template-columns:repeat(2,1fr)}\n}\n@media(max-width:750px){\n .app{grid-template-columns:72px 1fr}.sidebar .nav button span:not(.icon),.library-head>span,.filters,.library-search,.lib-text{display:none}\n .library-head{justify-content:center}.library-list{padding:0 8px}.lib-item{justify-content:center}.player{grid-template-columns:1fr 1fr}.player-right{display:none}.current-info{display:none}\n}\n\n.album-hero{display:flex;gap:25px;align-items:end;padding:25px 0 22px;border-bottom:1px solid #2a2a2a;margin-bottom:8px}\n.album-large-cover{width:220px;height:220px;object-fit:cover;border-radius:5px;box-shadow:0 8px 30px #0008;flex:none}\n.album-placeholder{background:linear-gradient(135deg,#0b5d2a,#1ed760);display:grid;place-items:center;font-size:85px}\n.album-info{min-width:0}.album-type{font-size:11px;font-weight:700;letter-spacing:.1em}.album-info h1{font-size:42px;margin:8px 0}.album-info p{color:#aaa}.album-actions{display:flex;gap:9px;align-items:center;flex-wrap:wrap}\n.album-actions .play{border-radius:999px;width:auto;height:40px;padding:0 20px;font-weight:700}\n.chip.danger{color:#ff7777}.chip.danger:hover{background:#4b2020}\n.remove-album-song{color:#888;font-size:20px;padding:3px 8px}.remove-album-song:hover{color:#ff7777}\n.album-card{cursor:pointer}\n.lyrics-panel{position:absolute;left:8px;right:8px;top:76px;bottom:100px;z-index:6;background:#121212;border-radius:8px;display:none;flex-direction:column;overflow:hidden;box-shadow:0 0 40px #000a}\n.lyrics-panel.open{display:flex}\n.lyrics-head{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid #2a2a2a;flex:none}\n.lyrics-head h2{margin:0;font-size:16px}\n.lyrics-controls{display:flex;gap:8px;align-items:center}\n.lyrics-body{flex:1;overflow-y:auto;padding:24px 20px 80px;text-align:center;scroll-behavior:smooth}\n.lyrics-line{padding:10px 12px;font-size:18px;line-height:1.45;color:#666;transition:color .2s,transform .2s,font-size .2s;border-radius:6px;cursor:default}\n.lyrics-line.active{color:#fff;font-size:22px;font-weight:700;transform:scale(1.02)}\n.lyrics-line.past{color:#888}\n.lyrics-plain{white-space:pre-wrap;text-align:left;font-size:15px;line-height:1.7;color:#ddd;max-width:640px;margin:0 auto}\n.lyrics-empty{color:#888;padding:40px;font-size:14px}\n.lyrics-loading{color:#aaa;padding:40px}\n.chip.lyrics-on{background:var(--green);color:#000}\n\n</style>\n</head>\n<body>\n<div class="app">\n  <aside class="sidebar">\n    <div class="nav">\n      <button class="active" data-page="home"><span class="icon">⌂</span><span>Home</span></button>\n      <button data-page="search"><span class="icon">⌕</span><span>Search</span></button>\n      <button data-page="albums"><span class="icon">▦</span><span>Albums</span></button>\n    </div>\n    <div class="library-head"><span>▥ &nbsp; Your Library</span><div class="actions"><button class="circle-btn" id="addPlaylist">＋</button><button class="circle-btn" id="collapseLib">↔</button></div></div>\n    <div class="filters">\n      <button class="chip active">All</button><button class="chip">Playlists</button><button class="chip">Artists</button><button class="chip">Albums</button>\n    </div>\n    <div class="library-search"><span>⌕</span><input id="libSearch" placeholder="Search in Your Library"></div>\n    <div class="library-list" id="libraryList"></div>\n  </aside>\n\n  <main class="main">\n    <div class="topbar">\n      <div class="nav-arrows"><button class="top-round" id="back">‹</button><button class="top-round" id="forward">›</button></div>\n      <div class="search"><span>⌕</span><input id="search" placeholder="What do you want to play?"></div>\n      <button class="circle-btn" title="Refresh library" id="refreshLibrary">↻</button><button class="circle-btn" title="Now Playing" id="toggleNow">♫</button>\n      <button class="circle-btn">◯</button>\n    </div>\n    <div class="content" id="content"></div>\n    <aside class="nowpanel" id="nowPanel"></aside>\n\n  <div class="lyrics-panel" id="lyricsPanel">\n    <div class="lyrics-head">\n      <h2>Lyrics</h2>\n      <div class="lyrics-controls">\n        <button class="chip" id="lyricsTimedBtn" title="Toggle timed lyrics">Timed</button>\n        <button class="circle-btn" id="closeLyrics" title="Close">×</button>\n      </div>\n    </div>\n    <div class="lyrics-body" id="lyricsBody"><div class="lyrics-empty">Play a song and open lyrics</div></div>\n  </div>\n  </main>\n\n  <div class="player">\n    <div class="current">\n      <img id="playerArt">\n      <div class="current-info"><div class="current-title" id="playerTitle">Nothing playing</div><div class="current-artist" id="playerArtist">Load some music to begin</div></div>\n      <button class="like" id="playerLike">♡</button>\n    </div>\n    <div class="player-center">\n      <div class="controls">\n        <button id="shuffle" title="Shuffle">⤨</button>\n        <button id="prev" title="Previous">|‹</button>\n        <button class="play" id="play">▶</button>\n        <button id="next" title="Next">›|</button>\n        <button id="repeat" title="Repeat">↻</button>\n      </div>\n      <div class="progress"><span id="elapsed">0:00</span><input class="range" id="seek" type="range" min="0" max="100" value="0"><span id="duration">0:00</span></div>\n    </div>\n    <div class="player-right">\n      <button id="lyricsBtn" title="Lyrics">🎤</button><button id="queueBtn" title="Queue">☷</button><button id="mute">🔊</button><input class="range volume" id="volume" type="range" min="0" max="1" step=".01" value=".8"><button id="fullscreen">⛶</button>\n    </div>\n  </div>\n</div>\n\n\n<audio id="audio"></audio>\n\n<script>\nconst $=s=>document.querySelector(s);\nconst audio=$("#audio");\nconst state={\n tracks:[],\n liked:JSON.parse(localStorage.getItem("spotifyLiked")||"[]"),\n playlists:JSON.parse(localStorage.getItem("spotifyPlaylists")||\'["My Playlist"]\'),\n albums:JSON.parse(localStorage.getItem("spotifyAlbums")||"{}"),\n current:-1, shuffle:false, repeat:false, query:"", history:[], future:[], albumView:null,\n lyrics:{plain:null,synced:null,lines:[],timed:true,loading:false,trackId:null}\n};\nconst gradients=[\n "linear-gradient(135deg,#7c2d12,#f59e0b)","linear-gradient(135deg,#172554,#2563eb)",\n "linear-gradient(135deg,#3f0d56,#d946ef)","linear-gradient(135deg,#064e3b,#34d399)",\n "linear-gradient(135deg,#450a0a,#ef4444)","linear-gradient(135deg,#312e81,#818cf8)"\n];\nfunction save(){localStorage.setItem("spotifyLiked",JSON.stringify(state.liked));localStorage.setItem("spotifyPlaylists",JSON.stringify(state.playlists));localStorage.setItem("spotifyAlbums",JSON.stringify(state.albums))}\nfunction art(t,i=0){return t.cover||""}\nfunction esc(s){return String(s).replace(/[&<>"\']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",\'"\':"&quot;","\'":"&#39;"}[m]))}\nfunction coverHTML(t,cls=""){\n  if(t.cover) return `<img class="${cls}" src="${esc(t.cover)}" loading="lazy">`;\n  return `<div class="${cls}" style="background:${gradients[t.index%gradients.length]};display:grid;place-items:center;font-size:${cls.includes("now")?"70":"28"}px;color:#fff">♫</div>`;\n}\nfunction fmt(x){if(!isFinite(x))return"0:00";x=Math.floor(x);return `${Math.floor(x/60)}:${String(x%60).padStart(2,"0")}`}\nfunction titleFromFile(name){return name.replace(/\\.[^/.]+$/,"").replace(/[_-]+/g," ").trim()}\nfunction current(){return state.tracks[state.current]}\nfunction playIndex(i,addHistory=true){\n if(!state.tracks[i])return;\n if(addHistory&&state.current>=0&&state.current!==i)state.history.push(state.current);\n state.current=i; const t=current(); audio.src=t.url; audio.play().catch(()=>{});\n state.lyrics={plain:null,synced:null,lines:[],timed:state.lyrics.timed,loading:false,trackId:null};\n if($("#lyricsPanel").classList.contains("open")) loadLyrics();\n render(); renderNow();\n}\nfunction next(){\n if(!state.tracks.length)return;\n let i=state.current;\n if(state.shuffle)i=Math.floor(Math.random()*state.tracks.length);\n else i=(i+1)%state.tracks.length;\n playIndex(i,false);\n}\nfunction prev(){if(audio.currentTime>4){audio.currentTime=0;return}let i=Math.max(0,state.current-1);playIndex(i,false)}\n\nfunction getAlbumMap(){\n  const map={};\n  state.tracks.forEach(t=>{\n    const key=t.album||"Music folder";\n    if(!map[key]) map[key]={name:key, tracks:[], cover:t.cover, artist:t.artist};\n    map[key].tracks.push(t);\n    if(!map[key].cover && t.cover) map[key].cover=t.cover;\n  });\n  return map;\n}\n\nfunction albumsLibraryHTML(){\n  const map=getAlbumMap();\n  const q=($("#libSearch").value||"").toLowerCase();\n  return Object.values(map).filter(a=>a.name.toLowerCase().includes(q)).map(a=>{\n    const cover=a.cover?`<img class="cover-sm" src="${esc(a.cover)}" loading="lazy">`:`<div class="cover-sm" style="background:${gradients[0]};display:grid;place-items:center;color:#fff">♫</div>`;\n    return `<div class="lib-item album-lib-item" data-album="${esc(a.name)}">${cover}<div class="lib-text"><div class="lib-title">${esc(a.name)}</div><div class="lib-sub">${a.tracks.length} song${a.tracks.length!==1?"s":""} · Album</div></div></div>`;\n  }).join("");\n}\n\nfunction renderLibrary(){\n const q=$("#libSearch").value.toLowerCase();\n const songItems=state.tracks.filter(t=>(t.title+" "+t.artist).toLowerCase().includes(q)).map(t=>{\n   const real=state.tracks.indexOf(t);\n   return `<div class="lib-item" data-i="${real}">${coverHTML(t,"cover-sm")}<div class="lib-text"><div class="lib-title">${esc(t.title)}</div><div class="lib-sub">${esc(t.artist||"Unknown artist")} · Song</div></div></div>`\n }).join("");\n const albumItems=albumsLibraryHTML();\n $("#libraryList").innerHTML=(albumItems?`<div style="padding:6px 8px 3px;color:#777;font-size:10px;text-transform:uppercase;letter-spacing:.08em">Albums</div>${albumItems}`:"")+\n (songItems?`<div style="padding:10px 8px 3px;color:#777;font-size:10px;text-transform:uppercase;letter-spacing:.08em">Songs</div>${songItems}`:"")+\n (!albumItems&&!songItems?`<div class="empty">Your Library is empty.</div>`:"");\n document.querySelectorAll(".lib-item[data-i]").forEach(x=>x.onclick=()=>playIndex(+x.dataset.i));\n document.querySelectorAll(".album-lib-item").forEach(x=>x.onclick=()=>showAlbum(x.dataset.album));\n}\n\nfunction homeHTML(){\n const recent=state.tracks.slice(0,6);\n const quick=recent.slice(0,6);\n return `<div class="hero"><h1>Good evening</h1>\n  <div class="quick-grid">${(quick.length?quick:sampleCards()).map((t,i)=>`<button class="quick" data-i="${state.tracks.length?state.tracks.indexOf(t):-1}">${coverHTML(t)}<span>${esc(t.title)}</span></button>`).join("")}</div>\n </div>\n <section class="section"><div class="section-head"><h2>Recently played</h2><span class="showall">Show all</span></div>\n <div class="cards">${(recent.length?recent:sampleCards()).map((t,i)=>card(t,state.tracks.length?state.tracks.indexOf(t):-1)).join("")}</div></section>\n <section class="section"><div class="section-head"><h2>Your music</h2><span class="showall">Browse your library</span></div>\n ${state.tracks.length?table(state.tracks):`<div class="empty">Put music files beside the server script (or in subfolders) and refresh the page.<br><br>Supported: MP3, FLAC, WAV, M4A, AAC, OGG, OPUS, WEBM</div>`}\n </section>`;\n}\n\nfunction sampleCards(){return [0,1,2,3,4].map((_,i)=>({title:["Your Music","Discover Weekly","Daily Mix","Liked Songs","My Playlist"][i],artist:"Spotify",index:i}))}\nfunction card(t,i){return `<div class="card" data-i="${i}">${coverHTML(t)}<div class="card-title">${esc(t.title)}</div><div class="card-sub">${esc(t.artist||"Playlist")}</div></div>`}\n\nfunction table(arr,albumMode=false){\n return `<table class="track-table"><thead><tr><th>#</th><th>Title</th><th>Artist</th><th>Album</th><th>♡</th>${albumMode?"<th></th>":""}</tr></thead><tbody>${arr.map((t,i)=>{\n   const globalIdx=state.tracks.indexOf(t);\n   return `<tr class="track-row ${globalIdx===state.current?"playing":""}" data-i="${globalIdx}"><td>${i+1}</td><td><div class="track-main">${coverHTML(t,"track-art")}<span>${esc(t.title)}</span></div></td><td>${esc(t.artist||"Unknown artist")}</td><td>${esc(t.album||"Local music")}</td><td><button class="like ${state.liked.includes(t.id)?"liked":""}" data-like="${t.id}">${state.liked.includes(t.id)?"♥":"♡"}</button></td>${albumMode?`<td></td>`:""}</tr>`;\n }).join("")}</tbody></table>`\n}\n\nfunction searchHTML(q){\n  const lower=q.toLowerCase();\n  const matches=state.tracks.filter(t=>(t.title+" "+t.artist+" "+(t.album||"")).toLowerCase().includes(lower));\n  if(!matches.length) return `<div class="empty">No results for “${esc(q)}”</div>`;\n  return `<div class="hero"><h1>Search results</h1><p style="color:#aaa">${matches.length} track${matches.length!==1?"s":""}</p></div>\n  <section class="section">${table(matches)}</section>`;\n}\n\nfunction albumsHTML(){\n  const map=getAlbumMap();\n  const albums=Object.values(map).sort((a,b)=>a.name.localeCompare(b.name));\n  if(!albums.length) return `<div class="empty">No albums found. Add music files with album tags or put them in folders.</div>`;\n  return `<div class="hero"><h1>Albums</h1></div>\n  <div class="cards">${albums.map(a=>{\n    const cover=a.cover?`<img src="${esc(a.cover)}" loading="lazy">`:`<div style="aspect-ratio:1;border-radius:5px;background:${gradients[0]};display:grid;place-items:center;font-size:48px;color:#fff">♫</div>`;\n    return `<div class="card album-card" data-album="${esc(a.name)}">${cover}<div class="card-title">${esc(a.name)}</div><div class="card-sub">${esc(a.artist||"Various")} · ${a.tracks.length} songs</div></div>`;\n  }).join("")}</div>`;\n}\n\nfunction wireAlbums(){\n  document.querySelectorAll(".album-card").forEach(x=>x.onclick=()=>showAlbum(x.dataset.album));\n}\n\nfunction showAlbum(name){\n  state.albumView=name;\n  const map=getAlbumMap();\n  const album=map[name];\n  if(!album){state.albumView=null;render();return;}\n  const cover=album.cover?`<img class="album-large-cover" src="${esc(album.cover)}">`:`<div class="album-large-cover album-placeholder">♫</div>`;\n  $("#content").innerHTML=`\n    <div class="album-hero">\n      ${cover}\n      <div class="album-info">\n        <div class="album-type">ALBUM</div>\n        <h1>${esc(album.name)}</h1>\n        <p>${esc(album.artist||"Various artists")} · ${album.tracks.length} song${album.tracks.length!==1?"s":""}</p>\n        <div class="album-actions">\n          <button class="play" id="playAlbum">▶ Play</button>\n          <button class="chip" id="backToAlbums">← Back</button>\n        </div>\n      </div>\n    </div>\n    ${table(album.tracks)}`;\n  $("#playAlbum").onclick=()=>{\n    if(album.tracks.length){\n      const idx=state.tracks.indexOf(album.tracks[0]);\n      if(idx>=0) playIndex(idx);\n    }\n  };\n  $("#backToAlbums").onclick=()=>{state.albumView=null; $("#content").innerHTML=albumsHTML(); wireAlbums();};\n  document.querySelectorAll(".track-row").forEach(x=>x.onclick=e=>{if(e.target.closest(".like"))return;playIndex(+x.dataset.i)});\n  document.querySelectorAll("[data-like]").forEach(b=>b.onclick=e=>{e.stopPropagation();toggleLike(b.dataset.like)});\n}\n\nfunction render(){\n if(state.albumView){showAlbum(state.albumView);return}\n $("#content").innerHTML=state.query?searchHTML(state.query):homeHTML();\n document.querySelectorAll(".track-row").forEach(x=>x.onclick=e=>{if(e.target.closest(".like"))return;playIndex(+x.dataset.i)});\n document.querySelectorAll("[data-like]").forEach(b=>b.onclick=e=>{e.stopPropagation();toggleLike(b.dataset.like)});\n document.querySelectorAll(".card,.quick").forEach(x=>x.onclick=()=>{let i=+x.dataset.i;if(i>=0)playIndex(i)});\n renderLibrary(); updatePlayer();\n}\nfunction toggleLike(id){id=String(id);state.liked=state.liked.includes(id)?state.liked.filter(x=>x!==id):[...state.liked,id];save();render()}\nfunction updatePlayer(){\n const t=current();\n if(!t){$("#playerArt").style.background=gradients[0];$("#playerArt").removeAttribute("src");$("#playerTitle").textContent="Nothing playing";$("#playerArtist").textContent="Load some music to begin";return}\n if(t.cover){\n   $("#playerArt").src=t.cover;\n   $("#playerArt").style.background="";\n }else{\n   $("#playerArt").removeAttribute("src");\n   $("#playerArt").style.background=gradients[t.index%gradients.length];\n }\n $("#playerTitle").textContent=t.title;$("#playerArtist").textContent=t.artist||"Unknown artist";$("#play").textContent=audio.paused?"▶":"Ⅱ";$("#playerLike").textContent=state.liked.includes(t.id)?"♥":"♡";$("#playerLike").classList.toggle("liked",state.liked.includes(t.id))\n}\nfunction renderNow(){\n const t=current(); if(!t)return;\n $("#nowPanel").innerHTML=`<div class="now-head"><span>Now Playing</span><button class="circle-btn" onclick="$(\'#nowPanel\').classList.remove(\'open\')">×</button></div>\n ${coverHTML(t,"now-cover")}<div class="now-title">${esc(t.title)}</div><div class="now-artist">${esc(t.artist||"Unknown artist")}</div>\n <div class="now-section"><h3>About this track</h3><p>${esc(t.album||"Local music")} · ${esc(t.genre||"Music")}<br><br>This panel mirrors the Spotify-style Now Playing area and updates with the current track.</p></div>\n <div class="now-section"><h3>Queue</h3><p>${state.tracks.slice(Math.max(0,state.current),Math.min(state.tracks.length,state.current+5)).map(x=>esc(x.title)).join("<br>")||"Nothing queued"}</p></div>\n <div class="now-section" style="text-align:center"><button class="chip" id="nowLyricsBtn">🎤 Show lyrics</button></div>`;\n const btn=$("#nowLyricsBtn"); if(btn) btn.onclick=()=>{ $("#lyricsPanel").classList.add("open"); loadLyrics(); };\n}\n\n/* ===== Lyrics ===== */\nfunction parseLRC(text){\n  if(!text) return [];\n  const lines=[];\n  const re=/\\[(\\d{1,3}):(\\d{2})(?:\\.(\\d{1,3}))?\\](.*)/g;\n  let m;\n  const raw=text.split(/\\r?\\n/);\n  for(const line of raw){\n    re.lastIndex=0;\n    const times=[];\n    let lastIdx=0;\n    let mm;\n    while((mm=re.exec(line))!==null){\n      const min=+mm[1], sec=+mm[2], frac=mm[3]||"0";\n      const ms=frac.length===1?+frac*100:frac.length===2?+frac*10:+frac;\n      const t=min*60+sec+ms/1000;\n      times.push(t);\n      lastIdx=mm.index+mm[0].length;\n    }\n    const lyricText=line.replace(/\\[[\\d:.]+\\]/g,"").trim();\n    if(times.length && lyricText){\n      times.forEach(t=>lines.push({time:t, text:lyricText}));\n    } else if(!times.length && lyricText && !line.startsWith("[")){\n      // plain line without timestamp — keep for fallback display\n    }\n  }\n  lines.sort((a,b)=>a.time-b.time);\n  return lines;\n}\n\nasync function loadLyrics(){\n  const t=current();\n  if(!t){\n    $("#lyricsBody").innerHTML=\'<div class="lyrics-empty">Nothing playing</div>\';\n    return;\n  }\n  if(state.lyrics.trackId===t.id && (state.lyrics.plain||state.lyrics.synced||state.lyrics.lines.length)){\n    renderLyrics();\n    return;\n  }\n  state.lyrics.loading=true;\n  state.lyrics.trackId=t.id;\n  $("#lyricsBody").innerHTML=\'<div class="lyrics-loading">Fetching lyrics…</div>\';\n  const duration=audio.duration && isFinite(audio.duration)?Math.round(audio.duration):"";\n  const params=new URLSearchParams({\n    track:t.title||"",\n    artist:t.artist||"",\n    album:t.album||"",\n    id:t.id||"",\n  });\n  if(duration) params.set("duration", duration);\n  try{\n    const r=await fetch("/api/lyrics?"+params.toString());\n    const data=await r.json();\n    state.lyrics.plain=data.plain||null;\n    state.lyrics.synced=data.synced||null;\n    state.lyrics.lines=parseLRC(data.synced);\n    state.lyrics.loading=false;\n    if(data.instrumental){\n      $("#lyricsBody").innerHTML=\'<div class="lyrics-empty">Instrumental — no lyrics</div>\';\n      return;\n    }\n    if(data.error && !data.plain && !data.synced){\n      $("#lyricsBody").innerHTML=`<div class="lyrics-empty">${esc(data.error||"No lyrics found")}<br><br><span style="font-size:12px;color:#666">Try songs with correct title & artist tags</span></div>`;\n      return;\n    }\n    renderLyrics();\n  }catch(e){\n    state.lyrics.loading=false;\n    $("#lyricsBody").innerHTML=`<div class="lyrics-empty">Failed to load lyrics<br><span style="font-size:12px">${esc(String(e))}</span></div>`;\n  }\n}\n\nfunction renderLyrics(){\n  const body=$("#lyricsBody");\n  const useTimed=state.lyrics.timed && state.lyrics.lines.length>0;\n  $("#lyricsTimedBtn").classList.toggle("lyrics-on", state.lyrics.timed);\n  $("#lyricsTimedBtn").textContent=state.lyrics.timed?"Timed ✓":"Timed";\n\n  if(useTimed){\n    body.innerHTML=state.lyrics.lines.map((l,i)=>\n      `<div class="lyrics-line" data-i="${i}" data-time="${l.time}">${esc(l.text)}</div>`\n    ).join("");\n    updateLyricsHighlight();\n  } else if(state.lyrics.plain){\n    body.innerHTML=`<div class="lyrics-plain">${esc(state.lyrics.plain)}</div>`;\n  } else if(state.lyrics.synced){\n    // show synced as plain (strip timestamps)\n    const plain=state.lyrics.synced.replace(/\\[[\\d:.]+\\]/g,"").replace(/\\n{3,}/g,"\\n\\n").trim();\n    body.innerHTML=`<div class="lyrics-plain">${esc(plain)}</div>`;\n  } else {\n    body.innerHTML=\'<div class="lyrics-empty">No lyrics available</div>\';\n  }\n}\n\nfunction updateLyricsHighlight(){\n  if(!state.lyrics.timed || !state.lyrics.lines.length) return;\n  const t=audio.currentTime;\n  const lines=state.lyrics.lines;\n  let active=-1;\n  for(let i=0;i<lines.length;i++){\n    if(lines[i].time<=t) active=i;\n    else break;\n  }\n  const els=document.querySelectorAll(".lyrics-line");\n  els.forEach((el,i)=>{\n    el.classList.remove("active","past");\n    if(i===active) el.classList.add("active");\n    else if(i<active) el.classList.add("past");\n  });\n  if(active>=0 && els[active]){\n    const body=$("#lyricsBody");\n    const el=els[active];\n    const bodyRect=body.getBoundingClientRect();\n    const elRect=el.getBoundingClientRect();\n    if(elRect.top<bodyRect.top+80 || elRect.bottom>bodyRect.bottom-80){\n      el.scrollIntoView({behavior:"smooth", block:"center"});\n    }\n  }\n}\n\n$("#play").onclick=()=>{if(!current()){ if(state.tracks.length) playIndex(0); return } audio.paused?audio.play():audio.pause()}\n$("#next").onclick=next;$("#prev").onclick=prev;\n$("#shuffle").onclick=()=>{state.shuffle=!state.shuffle;$("#shuffle").style.color=state.shuffle?"var(--green)":""}\n$("#repeat").onclick=()=>{state.repeat=!state.repeat;$("#repeat").style.color=state.repeat?"var(--green)":""}\n$("#volume").oninput=e=>audio.volume=e.target.value;\n$("#mute").onclick=()=>{audio.muted=!audio.muted;$("#mute").textContent=audio.muted?"🔇":"🔊"}\n$("#seek").oninput=e=>{if(audio.duration)audio.currentTime=audio.duration*(e.target.value/100)}\naudio.ontimeupdate=()=>{\n  if(audio.duration){\n    $("#seek").value=audio.currentTime/audio.duration*100;\n    $("#elapsed").textContent=fmt(audio.currentTime);\n    $("#duration").textContent=fmt(audio.duration);\n  }\n  if($("#lyricsPanel").classList.contains("open") && state.lyrics.timed) updateLyricsHighlight();\n};\naudio.onplay=updatePlayer;audio.onpause=updatePlayer;\naudio.onended=()=>state.repeat?playIndex(state.current,false):next();\n$("#refreshLibrary").onclick=()=>loadLibrary();\n$("#toggleNow").onclick=()=>{$("#nowPanel").classList.toggle("open");renderNow()}\n$("#queueBtn").onclick=()=>{$("#nowPanel").classList.add("open");renderNow()}\n$("#playerLike").onclick=()=>current()&&toggleLike(current().id);\n$("#search").oninput=e=>{state.query=e.target.value.trim();render()}\n$("#libSearch").oninput=renderLibrary;\n$("#addPlaylist").onclick=()=>{const n=prompt("Playlist name:");if(n){state.playlists.push(n);save();alert("Created “"+n+"” locally in this browser.")}}\n$("#collapseLib").onclick=()=>document.querySelector(".sidebar").classList.toggle("compact");\n$("#fullscreen").onclick=()=>document.documentElement.requestFullscreen?.();\n$("#back").onclick=()=>{state.future.push(location.hash);history.back()}\n$("#forward").onclick=()=>history.forward();\ndocument.querySelectorAll(".nav button").forEach(b=>b.onclick=()=>{\n document.querySelectorAll(".nav button").forEach(x=>x.classList.remove("active"));\n b.classList.add("active"); state.query="";$("#search").value="";state.albumView=null;\n if(b.dataset.page==="search") $("#search").focus();\n else if(b.dataset.page==="albums"){ $("#content").innerHTML=albumsHTML();wireAlbums(); }\n else render();\n});\n\n// Lyrics UI\n$("#lyricsBtn").onclick=()=>{\n  const panel=$("#lyricsPanel");\n  panel.classList.toggle("open");\n  if(panel.classList.contains("open")) loadLyrics();\n};\n$("#closeLyrics").onclick=()=>$("#lyricsPanel").classList.remove("open");\n$("#lyricsTimedBtn").onclick=()=>{\n  state.lyrics.timed=!state.lyrics.timed;\n  renderLyrics();\n};\n\nasync function loadLibrary(){\n  try{\n    const r=await fetch("/api/music");\n    if(!r.ok) throw new Error("HTTP "+r.status);\n    state.tracks=await r.json();\n    state.tracks.forEach((t,i)=>t.index=i);\n    render();\n  }catch(e){\n    console.error(e);\n    $("#content").innerHTML=\'<div class="empty">Could not load the music library.<br><br>Make sure the Python server is running.</div>\';\n    renderLibrary();\n  }\n}\naudio.volume=.8;\nloadLibrary();\n</script>\n\n</body>\n</html>'


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


def title_from_filename(path):
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.name


def safe_relative(path):
    try:
        return path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        return None


def find_sidecar_cover(audio_path):
    """Find common folder/song artwork without requiring any Python packages."""
    candidates = []

    # Album/folder artwork.
    for name in ("cover", "folder", "album", "front"):
        for ext in IMAGE_EXTS:
            candidates.append(audio_path.parent / (name + ext))

    # Artwork matching the exact audio filename.
    for ext in IMAGE_EXTS:
        candidates.append(audio_path.with_suffix(ext))

    for candidate in candidates:
        if candidate.is_file():
            rel = safe_relative(candidate)
            if rel:
                return "/art/" + quote(rel.as_posix(), safe="/")

    return None


def embedded_cover(audio_path):
    """
    Return a data URL for embedded artwork when Mutagen is available.
    The player still works without Mutagen; sidecar artwork is always supported.
    """
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return None

    try:
        audio = MutagenFile(str(audio_path))

        # MP3 / ID3 APIC
        if audio is not None and hasattr(audio, "tags") and audio.tags:
            try:
                apic = audio.tags.getall("APIC")
                if apic:
                    item = apic[0]
                    mime = item.mime or "image/jpeg"
                    return "data:" + mime + ";base64," + base64.b64encode(item.data).decode("ascii")
            except Exception:
                pass

        # FLAC / Ogg Vorbis pictures
        if audio is not None and hasattr(audio, "pictures") and audio.pictures:
            pic = audio.pictures[0]
            mime = getattr(pic, "mime", None) or "image/jpeg"
            data = getattr(pic, "data", None)
            if data:
                return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")

        # MP4 / M4A
        if audio is not None and hasattr(audio, "tags") and audio.tags:
            covr = audio.tags.get("covr")
            if covr:
                data = bytes(covr[0])
                mime = "image/png" if data.startswith(b"\x89PNG") else "image/jpeg"
                return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")

    except Exception:
        pass

    return None


def metadata(audio_path):
    title = title_from_filename(audio_path)
    artist = "Local music"
    album = "Music folder"
    genre = "Music"

    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(audio_path), easy=True)
        if audio:
            tags = audio

            def first(key, default):
                value = tags.get(key)
                if isinstance(value, list) and value:
                    return str(value[0])
                if value:
                    return str(value)
                return default

            title = first("title", title)
            artist = first("artist", artist)
            album = first("album", album)
            genre = first("genre", genre)
    except Exception:
        # Metadata is optional. Filename/folder info is enough to play music.
        pass

    cover = embedded_cover(audio_path) or find_sidecar_cover(audio_path)

    return title, artist, album, genre, cover


def scan_music():
    tracks = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
            continue

        rel = path.relative_to(ROOT)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue

        title, artist, album, genre, cover = metadata(path)

        tracks.append({
            "id": rel.as_posix(),
            "title": title,
            "artist": artist,
            "album": album,
            "genre": genre,
            "url": "/music/" + quote(rel.as_posix(), safe="/"),
            "cover": cover,
        })

    tracks.sort(key=lambda x: (
        x["artist"].lower(),
        x["album"].lower(),
        x["title"].lower()
    ))

    for i, track in enumerate(tracks):
        track["index"] = i

    return tracks




# ---------------------------------------------------------------------------
# Lyrics: local sidecar files + LRCLIB online fetch
# ---------------------------------------------------------------------------
# Sidecar path: same folder as the audio file, named "<stem>.lyrics.json"
# Example:  Music/Artist/Song.mp3  →  Music/Artist/Song.lyrics.json
#
# On startup the server scans for missing sidecars and fetches them in the
# background (rate-limited) so most tracks already have lyrics when you open
# the player.

_LYRICS_CACHE = {}  # in-memory: track_id -> result dict
_LYRICS_FETCH_LOCK = None  # set in main() if needed


def lyrics_sidecar_path(audio_rel_posix: str) -> Path:
    """Return Path for the .lyrics.json sidecar next to the audio file."""
    p = ROOT / audio_rel_posix
    return p.with_name(p.stem + ".lyrics.json")


def load_local_lyrics(track_id: str):
    """Load lyrics from sidecar JSON if present. track_id is relative posix path."""
    try:
        side = lyrics_sidecar_path(track_id)
        if side.is_file():
            data = json.loads(side.read_text(encoding="utf-8"))
            return {
                "plain": data.get("plain") or None,
                "synced": data.get("synced") or None,
                "instrumental": bool(data.get("instrumental")),
                "source": data.get("source") or "local",
                "id": data.get("id"),
                "local": True,
            }
    except Exception:
        pass
    return None


def save_local_lyrics(track_id: str, result: dict):
    """Persist lyrics next to the audio file."""
    if not result or result.get("error"):
        return False
    # Don't save pure errors
    if not result.get("plain") and not result.get("synced") and not result.get("instrumental"):
        return False
    try:
        side = lyrics_sidecar_path(track_id)
        payload = {
            "plain": result.get("plain"),
            "synced": result.get("synced"),
            "instrumental": bool(result.get("instrumental")),
            "source": result.get("source") or "lrclib",
            "id": result.get("id"),
            "track_id": track_id,
        }
        side.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        print(f"  Could not save lyrics for {track_id}: {e}")
        return False


def fetch_lyrics_online(track_name, artist_name, album_name="", duration=None):
    """Fetch plain + synced lyrics from LRCLIB (free, no API key)."""
    track_name = (track_name or "").strip()
    artist_name = (artist_name or "").strip()
    album_name = (album_name or "").strip()
    if not track_name:
        return {"error": "Missing track name", "plain": None, "synced": None, "instrumental": False}

    def _get(params):
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
        url = "https://lrclib.net/api/get?" + qs
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "SpotifyLANMusicPlayer/1.1 (local; lyrics-cache)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "plain": data.get("plainLyrics") or None,
                    "synced": data.get("syncedLyrics") or None,
                    "instrumental": bool(data.get("instrumental")),
                    "source": "lrclib",
                    "id": data.get("id"),
                }
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        except Exception:
            return None

    def _search(params):
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
        url = "https://lrclib.net/api/search?" + qs
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "SpotifyLANMusicPlayer/1.1 (local; lyrics-cache)",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                results = json.loads(resp.read().decode("utf-8"))
                if not results:
                    return None
                best = None
                for item in results:
                    if item.get("syncedLyrics"):
                        best = item
                        break
                if best is None:
                    best = results[0]
                return {
                    "plain": best.get("plainLyrics") or None,
                    "synced": best.get("syncedLyrics") or None,
                    "instrumental": bool(best.get("instrumental")),
                    "source": "lrclib-search",
                    "id": best.get("id"),
                }
        except Exception:
            return None

    params = {
        "track_name": track_name,
        "artist_name": artist_name or "Unknown",
    }
    if album_name and album_name not in ("Music folder", "Local music"):
        params["album_name"] = album_name
    if duration and 1 <= float(duration) <= 3600:
        params["duration"] = int(round(float(duration)))

    result = _get(params)
    if result is None and "duration" in params:
        del params["duration"]
        result = _get(params)
    if result is None:
        result = _search({
            "track_name": track_name,
            "artist_name": artist_name or "",
        })
    if result is None:
        result = {
            "error": "No lyrics found",
            "plain": None,
            "synced": None,
            "instrumental": False,
        }
    return result


def fetch_lyrics(track_name, artist_name, album_name="", duration=None, track_id=None):
    """
    Resolve lyrics: local sidecar → memory cache → online → save locally.
    track_id is the relative posix path of the audio file (used for sidecar).
    """
    # 1. Local file
    if track_id:
        local = load_local_lyrics(track_id)
        if local is not None:
            _LYRICS_CACHE[track_id] = local
            return local

    # 2. Memory cache
    cache_key = track_id or f"{artist_name}|{track_name}|{album_name}|{duration or 0}"
    if cache_key in _LYRICS_CACHE:
        return _LYRICS_CACHE[cache_key]

    # 3. Online
    result = fetch_lyrics_online(track_name, artist_name, album_name, duration)

    # 4. Save locally when we have something useful
    if track_id and (result.get("plain") or result.get("synced") or result.get("instrumental")):
        if save_local_lyrics(track_id, result):
            result["local"] = True
            result["source"] = (result.get("source") or "lrclib") + "+saved"

    _LYRICS_CACHE[cache_key] = result
    if len(_LYRICS_CACHE) > 400:
        _LYRICS_CACHE.pop(next(iter(_LYRICS_CACHE)))
    return result


def prefetch_missing_lyrics(tracks, delay=0.35):
    """
    Background: for every track without a local sidecar, fetch from LRCLIB
    and save. Rate-limited to be polite to the free API.
    """
    import time
    import threading

    missing = []
    for t in tracks:
        tid = t.get("id")
        if not tid:
            continue
        if load_local_lyrics(tid) is None:
            missing.append(t)

    if not missing:
        print(f" Lyrics      : all {len(tracks)} tracks already cached locally")
        return

    print(f" Lyrics      : {len(missing)} missing — fetching in background…")

    def worker():
        ok = 0
        fail = 0
        for i, t in enumerate(missing):
            tid = t["id"]
            # Skip if another request already saved it
            if load_local_lyrics(tid) is not None:
                ok += 1
                continue
            try:
                result = fetch_lyrics_online(
                    t.get("title") or "",
                    t.get("artist") or "",
                    t.get("album") or "",
                    None,  # duration unknown at scan time without mutagen probing
                )
                if result.get("plain") or result.get("synced") or result.get("instrumental"):
                    if save_local_lyrics(tid, result):
                        ok += 1
                        _LYRICS_CACHE[tid] = {**result, "local": True}
                    else:
                        fail += 1
                else:
                    # Cache negative result briefly so we don't retry forever this session
                    _LYRICS_CACHE[tid] = result
                    fail += 1
            except Exception as e:
                fail += 1
                print(f"  Lyrics fetch error ({tid}): {e}")
            if (i + 1) % 10 == 0 or (i + 1) == len(missing):
                print(f"  Lyrics progress: {i+1}/{len(missing)} (saved {ok}, no-match/fail {fail})")
            time.sleep(delay)
        print(f" Lyrics done  : saved {ok}, no match/fail {fail}")

    threading.Thread(target=worker, daemon=True).start()


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        if self.path.startswith("/api/"):
            print("%s - %s" % (self.address_string(), fmt % args))

    def _serve_file(self, path):
        """Serve a file with HTTP Range support (needed for seeking in the player)."""
        import os as _os
        size = path.stat().st_size
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        range_header = self.headers.get("Range")

        if range_header:
            # Parse bytes=start-end
            try:
                units, rng = range_header.strip().split("=", 1)
                if units != "bytes":
                    raise ValueError
                start_s, end_s = (rng + "-").split("-", 1)[:2]
                start = int(start_s) if start_s else 0
                end = int(end_s) if end_s else size - 1
                end = min(end, size - 1)
                if start > end or start >= size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    return
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Length", str(length))
                self.send_header("Content-Type", mime)
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                with open(path, "rb") as f:
                    f.seek(start)
                    remaining = length
                    while remaining > 0:
                        chunk = f.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                return
            except Exception:
                pass  # fall through to full file

        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)

    def do_GET(self):
        parsed = urlparse(self.path)

        # Embedded player.
        if parsed.path in ("", "/"):
            data = PLAYER_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return


        # Lyrics (local cache + LRCLIB)
        if parsed.path == "/api/lyrics":
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query)
            track = (qs.get("track") or [""])[0]
            artist = (qs.get("artist") or [""])[0]
            album = (qs.get("album") or [""])[0]
            duration = (qs.get("duration") or [None])[0]
            track_id = (qs.get("id") or [None])[0]  # relative path of the audio file
            try:
                result = fetch_lyrics(track, artist, album, duration, track_id=track_id)
            except Exception as e:
                result = {"error": str(e), "plain": None, "synced": None, "instrumental": False}
            data = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=60")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # Dynamic library.
        if parsed.path == "/api/music":
            data = json.dumps(scan_music(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # Artwork sidecars.
        if parsed.path.startswith("/art/"):
            rel = unquote(parsed.path[len("/art/"):])
            target = (ROOT / rel).resolve()
            if safe_relative(target) is None or not target.is_file():
                self.send_error(404, "Artwork not found")
                return
            if target.suffix.lower() not in IMAGE_EXTS:
                self.send_error(403, "Not an image")
                return

            data = target.read_bytes()
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Cache-Control", "public, max-age=3600")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return

        # Audio streaming.
        if parsed.path.startswith("/music/"):
            rel = unquote(parsed.path[len("/music/"):])
            target = (ROOT / rel).resolve()

            if safe_relative(target) is None:
                self.send_error(403, "Forbidden")
                return

            if not target.is_file() or target.suffix.lower() not in AUDIO_EXTS:
                self.send_error(404, "Music file not found")
                return

            # Serve file with Range support from ROOT (not process cwd)
            try:
                self._serve_file(target)
            except Exception as e:
                self.send_error(500, str(e))
            return

        self.send_error(404, "Not found")


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    ip = lan_ip()
    tracks = scan_music()
    count = len(tracks)
    # Background-fetch any lyrics not yet saved locally
    try:
        prefetch_missing_lyrics(tracks)
    except Exception as e:
        print(f" Lyrics prefetch could not start: {e}")

    print()
    print("=" * 64)
    print(" Spotify LAN Music Player")
    print("=" * 64)
    print(f" Music folder : {ROOT}")
    print(f" Music files  : {count}")
    print()
    print(f" This PC      : http://127.0.0.1:{PORT}/")
    print(f" LAN          : http://{ip}:{PORT}/")
    print()
    print(" The entire player is contained in this ONE Python file.")
    print(" Music is scanned recursively from this folder.")
    print(" Press Ctrl+C to stop.")
    print("=" * 64)
    print()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
