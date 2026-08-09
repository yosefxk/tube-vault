# ⚡ TubeVault

<p align="center">
  <img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white" alt="Docker Ready">
  <img src="https://img.shields.io/badge/Tailscale-Ready-000000.svg?logo=tailscale&logoColor=white" alt="Tailscale Ready">
</p>

**TubeVault** is a lightweight, modern, self-hosted web application for fast media downloading built for personal servers, **Portainer**, and **Tailscale**. Inspired by Radarr/Sonarr UI aesthetics, TubeVault lets you paste any YouTube or media link on your phone or desktop, pick quality choices (MP3 320k, 1080p, 4K), convert content, download files directly onto your device, and maintain a persistent history of all past downloads.

---

## ✨ Features

- 📱 **Mobile-First & Pain-Free UI**: Clean dark glassmorphic design optimized for smartphone touchscreens (iOS Safari, Android Chrome) and desktop monitors.
- ⚡ **1-Tap Quick Action Buttons**: Instant download triggers for **`Quick MP3 (320kbps)`** and **`Quick 1080p Video`**.
- 📋 **Auto-Paste Clipboard Integration**: One-click paste from your phone's clipboard straight into the input bar.
- 🚀 **Multi-Threaded Downloader**: Powered by `yt-dlp` with fragment downloading (`-N 8`) and `FFmpeg` for maximum server speed.
- 📥 **Zero-Click Device Download**: Once conversion completes on your server, the file automatically triggers a direct browser save onto your phone/laptop.
- 📜 **Persistent History Database**: Remembers every video you've downloaded with title, thumbnail, channel, date, format, and file size. Re-download past files to any device anytime.
- 🔒 **Tailscale & Homelab Private**: Exposes a single internal port (`5000`) perfect for private access via Tailscale (`http://100.x.x.x:5000`) without public exposure.

---

## 🐋 Deployment via Portainer (Recommended)

To run **TubeVault** in **Portainer** on your server:

1. Open **Portainer** -> Go to **Stacks** -> **Add stack**.
2. Name the stack `tube-vault`.
3. Paste the following Stack definition:

```yaml
version: '3.8'

services:
  tube-vault:
    image: ghcr.io/yosefxk/tube-vault:latest  # or build locally from git
    container_name: tube-vault
    restart: unless-stopped
    ports:
      - "5000:5000"
    volumes:
      - /path/to/server/downloads:/app/downloads
      - /path/to/server/data:/app/data
    environment:
      - PORT=5000
      - HOST=0.0.0.0
```

4. Click **Deploy the stack**.

---

## 🔒 Accessing via Tailscale

Since TubeVault is designed for personal server hosting:
- You can access it securely from anywhere on your phone or laptop using your server's **Tailscale IP**:
  ```text
  http://100.100.1.2:5000
  ```
  *(or your Tailscale MagicDNS name: `http://server-name.your-tailnet.ts.net:5000`)*
- No need to expose ports to the public internet!

---

## 💻 Local Docker Compose

If running directly on your Linux/Mac/Windows host:

```bash
# Clone the repository
git clone https://github.com/yosefxk/tube-vault.git
cd tube-vault

# Start container
docker-compose up -d
```

Open `http://localhost:5000` in your browser.

---

## 🛠️ Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PORT` | `5000` | Internal server port to expose |
| `HOST` | `0.0.0.0` | Server host binding |
| `DOWNLOAD_DIR` | `/app/downloads` | Server directory where converted files are stored |
| `DATA_DIR` | `/app/data` | Server directory for `history.json` database |

---

## 📁 Repository Architecture

```
tube-vault/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI server, REST & SSE stream endpoints
│   ├── downloader.py        # Async yt-dlp multi-threaded engine & progress hooks
│   ├── db.py                # Thread-safe persistent JSON history database
│   └── config.py            # Environment configuration settings
├── static/
│   ├── css/
│   │   └── style.css        # Responsive dark space glassmorphism styling
│   ├── js/
│   │   └── app.js           # UI logic, SSE tracking, auto-download & history
│   └── index.html           # Single-Page Web Application
├── downloads/               # Server media storage
├── data/
│   └── history.json         # Download history database
├── Dockerfile               # Production container definition
├── docker-compose.yml       # Docker compose setup
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
└── run.py                   # Server entrypoint
```

---

## 📄 License

This project is open source under the [MIT License](LICENSE).
