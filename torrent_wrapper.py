import sys
import os
import asyncio
import threading
import time
import queue
from io import StringIO
# Import your existing modules from the subdirectory
from torrent_client.parser import bdecode
from torrent_client.connect_to_peer_async import TorrentDownloader
from torrent_client.get_peers import get_peers_from_tracker

class LogCapture(StringIO):
    """Captures standard output to send to the web UI."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def write(self, string):
        if string.strip():
            self.log_queue.put(string.strip())
        sys.__stdout__.write(string) # Also print to real terminal

class TorrentManager:
    """Singleton to manage the async torrent task and state."""
    def __init__(self):
        self.loop = None
        self.thread = None
        self.download_task = None
        self.stop_event = None
        self.log_queue = queue.Queue()
        
        # State visible to frontend
        self.state = {
            "status": "IDLE", # IDLE, RUNNING, COMPLETED, ERROR
            "filename": "",
            "total_size": 0,
            "downloaded_bytes": 0,
            "progress_percent": 0.0,
            "peers_connected": 0,
            "speed_kbps": 0.0,
            "logs": []
        }
        
        # Internal metrics for speed calc
        self.last_bytes = 0
        self.last_time = time.time()

    def start_download(self, torrent_path, download_root):
        if self.thread and self.thread.is_alive():
            return False

        self.reset_state()
        self.state["status"] = "RUNNING"

        # Determine output path from torrent metadata
        info = get_torrent_output_info(torrent_path)

        if info["type"] == "single":
            output_path = os.path.join(download_root, info["name"])
            self.state["filename"] = info["name"]
        else:
            output_path = os.path.join(download_root, info["folder"])
            self.state["filename"] = info["folder"]

        # Capture stdout
        sys.stdout = LogCapture(self.log_queue)

        # Start background thread
        self.thread = threading.Thread(
            target=self._run_async_loop,
            args=(torrent_path, output_path),
            daemon=True
        )
        self.thread.start()
        return True


    def stop_download(self):
        """Cancels the running task."""
        if self.loop and self.loop.is_running():
            # Schedule the cancellation in the loop safely
            self.loop.call_soon_threadsafe(self.download_task.cancel)
            self.state["status"] = "STOPPED"
            self.state["logs"].append("Download stopped by user.")

    def reset_state(self):
        self.state = {
            "status": "IDLE",
            "filename": "Initializing...",
            "total_size": 0,
            "downloaded_bytes": 0,
            "progress_percent": 0.0,
            "peers_connected": 0,
            "speed_kbps": 0.0,
            "logs": []
        }
        self.last_bytes = 0
        self.last_time = time.time()

    def _run_async_loop(self, torrent_path, output_path):
        """The worker function running in the separate thread."""
        asyncio.set_event_loop(asyncio.new_event_loop())
        self.loop = asyncio.get_event_loop()
        
        try:
            self.download_task = self.loop.create_task(
                self._download_workflow(torrent_path, output_path)
            )
            self.loop.run_until_complete(self.download_task)
        except asyncio.CancelledError:
            print("Task cancelled.")
        except Exception as e:
            self.state["status"] = "ERROR"
            print(f"Critical Error: {e}")
        finally:
            self.loop.close()
            sys.stdout = sys.__stdout__ # Restore stdout

    async def _download_workflow(self, torrent_path, output_path):
        """Orchestrates tracker lookup and file download."""
        try:
            print(f"Processing: {os.path.basename(torrent_path)}")
            
            # 1. Get Peers
            print("Contacting tracker...")
            peers = get_peers_from_tracker(torrent_path)
            if not peers:
                print("No peers found. Aborting.")
                self.state["status"] = "ERROR"
                return

            # 2. Initialize Downloader
            downloader = TorrentDownloader(torrent_path, peers, max_peers=50)
            
            # Update static info
            self.state["total_size"] = downloader.total_length

            # 3. Start Monitor Task (Polling)
            monitor = asyncio.create_task(self._monitor_progress(downloader))
            
            # 4. Start Download
            success = await downloader.download(output_path)
            
            monitor.cancel()
            
            if success:
                self.state["status"] = "COMPLETED"
                self.state["progress_percent"] = 100.0
                print("Download finished successfully.")
            else:
                self.state["status"] = "ERROR"
                print("Download finished incomplete.")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Workflow Error: {e}")
            self.state["status"] = "ERROR"

    async def _monitor_progress(self, downloader):
        """Polls the downloader object to update UI state."""
        while True:
            # Calculate metrics
            num_pieces = len(downloader.downloaded_pieces)
            total_pieces = downloader.num_pieces
            piece_length = downloader.piece_length
            
            current_bytes = num_pieces * piece_length
            # Fix for last piece usually being smaller
            if num_pieces == total_pieces:
                current_bytes = downloader.total_length
            
            # Speed Calculation
            now = time.time()
            duration = now - self.last_time
            if duration > 0:
                speed = (current_bytes - self.last_bytes) / duration / 1024 # KB/s
                self.state["speed_kbps"] = round(speed, 2)
            
            self.last_bytes = current_bytes
            self.last_time = now

            # Update State
            self.state["downloaded_bytes"] = current_bytes
            self.state["progress_percent"] = round((num_pieces / total_pieces) * 100, 1)
            self.state["peers_connected"] = len(downloader.connected_peers)
            
            await asyncio.sleep(0.5)

    def get_stream_data(self):
        """Yields current state as SSE data."""
        # Flush log queue into state
        new_logs = []
        while not self.log_queue.empty():
            new_logs.append(self.log_queue.get())
        
        # We only send new logs to save bandwidth, clearing them from state after sending
        # In a real app we might keep history, but here we just stream updates
        data = self.state.copy()
        data["logs"] = new_logs
        
        return data

def get_torrent_output_info(torrent_path):
    with open(torrent_path, 'rb') as f:
        data = bdecode(f.read())

    info = data[b'info']

    # Single-file torrent
    if b'length' in info:
        filename = info[b'name'].decode('utf-8')
        return {
            "type": "single",
            "name": filename
        }

    # Multi-file torrent
    elif b'files' in info:
        folder = info[b'name'].decode('utf-8')
        files = []
        for f in info[b'files']:
            path = [p.decode('utf-8') for p in f[b'path']]
            files.append("/".join(path))

        return {
            "type": "multi",
            "folder": folder,
            "files": files
        }


# Global Instance
manager = TorrentManager()