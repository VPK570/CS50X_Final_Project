import sys
import os
import asyncio
import threading
import time
import queue
from io import StringIO
from torrent_client.parser import bdecode
from torrent_client.connect_to_peer_async import TorrentDownloader
from torrent_client.get_peers import get_peers_from_tracker

class LogCapture(StringIO):
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def write(self, string):
        if string.strip():
            self.log_queue.put(string.strip())
        sys.__stdout__.write(string)

class TorrentManager:
    def __init__(self):
        self.loop = None
        self.thread = None
        self.download_task = None
        self.log_queue = queue.Queue()
        
        self.state = {
            "status": "IDLE",
            "filename": "",
            "total_size": 0,
            "downloaded_bytes": 0,
            "progress_percent": 0.0,
            "peers_connected": 0,
            "speed_kbps": 0.0,
            "logs": []
        }
        
        self.last_bytes = 0
        self.last_time = time.time()

    def start_download(self, torrent_path, download_root):
        if self.thread and self.thread.is_alive():
            return False

        self.reset_state()
        self.state["status"] = "RUNNING"

        # [FIX] Extract real filename/extension here
        try:
            info = get_torrent_output_info(torrent_path)
            if info["type"] == "single":
                # Use the name from the torrent metadata (includes extension)
                target_name = info["name"]
                output_path = os.path.join(download_root, target_name)
                self.state["filename"] = target_name
            else:
                # Multi-file torrents create a folder
                target_name = info["folder"]
                output_path = os.path.join(download_root, target_name)
                self.state["filename"] = target_name
        except Exception as e:
            self.state["status"] = "ERROR"
            self.state["logs"].append(f"Metadata error: {str(e)}")
            return False

        sys.stdout = LogCapture(self.log_queue)

        self.thread = threading.Thread(
            target=self._run_async_loop,
            args=(torrent_path, output_path),
            daemon=True
        )
        self.thread.start()
        return True

    def stop_download(self):
        if self.loop and self.loop.is_running():
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
            sys.stdout = sys.__stdout__

    async def _download_workflow(self, torrent_path, output_path):
        try:
            print(f"Processing: {os.path.basename(torrent_path)}")
            
            print("Contacting tracker...")
            peers = get_peers_from_tracker(torrent_path)
            if not peers:
                print("No peers found. Aborting.")
                self.state["status"] = "ERROR"
                return

            downloader = TorrentDownloader(torrent_path, peers, max_peers=50)
            self.state["total_size"] = downloader.total_length

            monitor = asyncio.create_task(self._monitor_progress(downloader))
            
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
        while True:
            num_pieces = len(downloader.downloaded_pieces)
            total_pieces = downloader.num_pieces
            piece_length = downloader.piece_length
            
            current_bytes = num_pieces * piece_length
            if num_pieces == total_pieces:
                current_bytes = downloader.total_length
            
            now = time.time()
            duration = now - self.last_time
            if duration > 0:
                speed = (current_bytes - self.last_bytes) / duration / 1024 
                self.state["speed_kbps"] = round(speed, 2)
            
            self.last_bytes = current_bytes
            self.last_time = now

            self.state["downloaded_bytes"] = current_bytes
            self.state["progress_percent"] = round((num_pieces / total_pieces) * 100, 1)
            self.state["peers_connected"] = len(downloader.connected_peers)
            
            await asyncio.sleep(0.5)

    def get_stream_data(self):
        new_logs = []
        while not self.log_queue.empty():
            new_logs.append(self.log_queue.get())
        
        data = self.state.copy()
        data["logs"] = new_logs
        return data

def get_torrent_output_info(torrent_path):
    with open(torrent_path, 'rb') as f:
        data = bdecode(f.read())

    info = data[b'info']

    # Safely decode utf-8, ignoring errors to prevent crashes
    if b'length' in info:
        filename = info[b'name'].decode('utf-8', errors='ignore')
        return {
            "type": "single",
            "name": filename
        }
    elif b'files' in info:
        folder = info[b'name'].decode('utf-8', errors='ignore')
        files = []
        for f in info[b'files']:
            path = [p.decode('utf-8', errors='ignore') for p in f[b'path']]
            files.append("/".join(path))

        return {
            "type": "multi",
            "folder": folder,
            "files": files
        }

manager = TorrentManager()