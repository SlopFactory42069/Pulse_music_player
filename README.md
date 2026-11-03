# Spotify LAN Music Player

A lightweight, self-hosted music player written in Python. It serves a Spotify-inspired web interface on your local network, so you can browse and play music stored on one computer from a browser on another device.

**No database, Node.js, build step, or separate frontend files are required.** The web interface is embedded in `Spotify.py`.

> This is an independent, unofficial project. It is not affiliated with, endorsed by, or connected to Spotify AB. “Spotify” is used only to describe the visual inspiration.

## Features

- Stream a local music collection over your LAN.
- Recursively scans the project folder and its subfolders for audio files.
- Supports MP3, FLAC, WAV, M4A, AAC, OGG, OPUS, WEBM, and OGA.
- Reads common audio tags and embedded artwork with the optional [Mutagen](https://mutagen.readthedocs.io/) package.
- Supports folder/song artwork such as `cover.jpg`, `folder.png`, and `song-name.jpg`.
- Browse and search tracks and albums.
- Playback controls, shuffle, repeat, seeking, volume, and liked songs.
- Fetches plain and synchronized lyrics from [LRCLIB](https://lrclib.net/).
- Saves fetched lyrics beside the corresponding audio file, allowing them to be reused offline.
- Uses Python's standard library for the web server and audio-file streaming.

## Requirements

- Python 3.8 or newer.
- A modern browser on the device used to play music.
- Devices must be able to reach the computer running the server on the same local network.
- Internet access is needed to fetch lyrics that are not already cached. Playback of local music does not require an internet connection once the page is reachable on your LAN.

Mutagen is optional. Without it, the player still works, but embedded tags and embedded album artwork may not be available. Filename-based titles and sidecar artwork will still work.

## Installation

### 1. Get the project

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd YOUR_REPOSITORY
```

Or download the repository as a ZIP and extract it.

### 2. (Recommended) Create a virtual environment

**Windows (PowerShell):**

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install the optional metadata dependency

```bash
python -m pip install -r requirements.txt
```

The application itself uses only Python's standard library. `requirements.txt` installs Mutagen to enable richer metadata and embedded artwork support; you can skip this step if you do not need those features.

## Add your music

Place `Spotify.py` in the folder you want to use as your music library, or put your music files in subfolders beneath it. The scanner searches recursively.

Example:

```text
YOUR_REPOSITORY/
├── Spotify.py
├── README.md
├── requirements.txt
├── .gitignore
└── Music/
    ├── Artist One/
    │   └── Album Name/
    │       ├── 01 - Song.mp3
    │       └── cover.jpg
    └── Artist Two/
        └── Another Song.flac
```

The current version scans from the folder containing `Spotify.py`. It does not require the folder to be named `Music`.

### Artwork lookup order

For each track, the player tries:

1. Embedded artwork (when Mutagen can read it).
2. `cover`, `folder`, `album`, or `front` image in the track's folder.
3. An image with the same filename as the audio file.
4. A built-in music-note placeholder.

Supported sidecar artwork formats: JPG, JPEG, PNG, and WEBP.

## Run the server

From the project folder:

```bash
python Spotify.py
```

The terminal prints a local address and, when detected, your LAN address. Open the LAN address from another device on the same network. For example:

```text
http://192.168.1.20:8000/
```

The address above is only an example; use the address printed by your own server.

To stop the server, press `Ctrl+C` in the terminal.

### Change the port

The default port is `8000`. You can override it with the `PULSE_PORT` environment variable.

**Windows (PowerShell):**

```powershell
$env:PULSE_PORT = "8080"
python Spotify.py
```

**Linux / macOS:**

```bash
PULSE_PORT=8080 python3 Spotify.py
```

Then visit the LAN address with `:8080` instead of `:8000`.

## Lyrics and offline use

When lyrics are requested, the server checks for a local sidecar file first. If one is not found, it queries LRCLIB and saves a successful result beside the song as:

```text
Song.lyrics.json
```

At startup, the application also attempts to fetch missing lyrics in the background. This requires internet access and may take a while for a large library. Songs without a matching LRCLIB entry will simply have no lyrics.

The `.gitignore` excludes these generated lyric cache files, so they are not accidentally committed with your source code.

## Network and security notes

- The server listens on all network interfaces so other devices on your LAN can connect.
- **There is no login, password, or user management.** Anyone who can reach the server can browse and stream the music it exposes.
- Use it only on a trusted private network. Do not expose the port directly to the public internet or configure router port forwarding for it.
- Your computer's firewall may ask whether Python should be allowed to accept local network connections. Allow access only on private/trusted networks if you want other devices to connect.
- The server is intended for personal/local use, not as a hardened public-facing service.

## Troubleshooting

### The page does not open on another device

1. Make sure the server is still running.
2. Use the LAN address printed in the terminal, not `127.0.0.1` (that address refers to the device you are currently using).
3. Check that both devices are on the same network and that client isolation is disabled on the Wi-Fi access point.
4. Check your computer's firewall and allow the selected TCP port on private networks.

### No music appears

- Check that the files use one of the supported extensions.
- Make sure the files are in the folder containing `Spotify.py` or one of its subfolders.
- Click the refresh button in the web interface after adding files.

### Missing tags or embedded artwork

Install Mutagen in the same Python environment used to run the application:

```bash
python -m pip install mutagen
```

### Lyrics do not appear

Lyrics depend on LRCLIB having a match for the track's title and artist. Check the audio tags if the match fails. Previously fetched lyrics can be loaded from their local `.lyrics.json` sidecar files.

## Project structure

```text
.
├── Spotify.py          # Python server and embedded web application
├── README.md           # Setup and usage instructions
├── requirements.txt    # Optional Mutagen dependency
└── .gitignore          # Excludes local music and generated files
```

## Contributing

Bug reports and improvements are welcome. If you submit a change, please include a short description of what changed and how you tested it.

## License

No license has been selected for this repository yet. Add a `LICENSE` file before publishing if you want to grant others explicit permission to use, modify, and redistribute the project.
