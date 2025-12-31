# PyTorrent – Simple BitTorrent Client with Web Dashboard

## 🎥 Video Demo
https://youtu.be/-bEryA4tv2g

---

## 📌 What is PyTorrent?

PyTorrent is a **Python-based BitTorrent client** with a **web interface**.  
Instead of running everything in a terminal, you can upload a `.torrent` file in your browser, start the download, and watch what’s happening in real time.

This project was built as a **CS50x Final Project** and focuses on:
- Understanding how BitTorrent works internally
- Using `asyncio` for real network-heavy tasks
- Connecting a low-level backend with a clean web UI

---

## 🧠 How It Works (High-Level)

PyTorrent has **two main parts**:

### 1️⃣ BitTorrent Engine (Backend Logic)
This part:
- Reads `.torrent` files
- Talks to trackers to find peers
- Connects to multiple peers at the same time
- Downloads files piece by piece
- Verifies each piece using SHA-1 hashing

### 2️⃣ Web Dashboard (Frontend + Controller)
This part:
- Lets users upload `.torrent` files
- Starts the download process
- Shows live logs and progress
- Keeps the app responsive while downloads run in the background

---

## 📁 Project Structure (Simple Explanation)

```
project/
│
├── app.py
│   → Flask web server and main entry point
│
├── torrent_wrapper.py
│   → Runs the async BitTorrent engine safely in the background
│
├── torrent_client/
│   ├── parser.py
│   │   → Decodes .torrent files (bencoding)
│   ├── get_peers.py
│   │   → Contacts trackers and finds peers
│   ├── connect_to_peer_async.py
│   │   → Handles peer connections and downloads
│   └── __init__.py
│
├── downloads/
│   → Final downloaded files
│
├── requirements.txt
│
└── README.md
```

---

## 🔍 Key Features Explained Simply

### ✅ Real BitTorrent Protocol
This project follows the **official BitTorrent specification (BEP 0003)** instead of using libraries like `libtorrent`.

### 🔐 File Verification (SHA-1)
Each downloaded piece is verified using SHA-1 hashing.  
If a piece is corrupted, it is discarded and downloaded again.

### 📡 Real-Time Updates (SSE)
The dashboard uses **Server-Sent Events (SSE)** to stream logs and progress updates live to the browser.

### 🧵 Async + Flask Bridge
Flask is synchronous, but BitTorrent is async.
A background thread runs an `asyncio` event loop so downloads don’t freeze the web server.

---

## ⚙️ Installation & Setup

### 1️⃣ Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate   # Mac/Linux
venv\Scripts\activate    # Windows
```

### 2️⃣ Install Dependencies

```bash
pip install Flask werkzeug
```

---

## ▶️ Running the App

```bash
python3 app.py
```

Then open:
```
http://127.0.0.1:5000
```

---

## 🧪 How to Use

1. Open the dashboard in your browser
2. Upload a `.torrent` file
3. Click **Start Download**
4. Watch logs and progress update live
5. Downloaded file appears in the `downloads/` folder

---

## 🙌 Final Words

PyTorrent helped me understand how real-world peer-to-peer systems work under the hood.  
It combines networking, concurrency, cryptography, and web development into one complete system.
