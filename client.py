import asyncio
import random
from torrent import Torrent
from tracker import TrackerManager
from piece_manager import PieceManager
from peer import PeerConnection
from file_handler import FileHandler
from utils import generate_peer_id


class TorrentClient:
    def __init__(self, torrent_file, save_path):
        self.peer_id = generate_peer_id()
        self.torrent = Torrent(torrent_file)
        self.torrent.peer_id = self.peer_id

        self.tracker_manager = TrackerManager(self.torrent)
        self.piece_manager = PieceManager(self.torrent)
        self.file_handler = FileHandler(self.torrent, save_path)

        self.peers = []
        self.all_candidates = []
        self.is_paused = False

    def toggle_pause(self):
        self.is_paused = not self.is_paused

    async def start(self):
        print("DEBUG: Contacting Trackers...")
        self.all_candidates = self.tracker_manager.get_peers()

        if not self.all_candidates:
            print("CRITICAL: No peers found.")
            return

        print(f"DEBUG: Found {len(self.all_candidates)} candidates. Engaging Nitro Mode...")
        await self._maintain_swarm()

    async def _maintain_swarm(self):
        # NITRO MODE: Higher Peer Limit (130)
        # Note: Too high might crash your home router. 130 is the sweet spot.
        MAX_ACTIVE_PEERS = 130

        while not self.piece_manager.complete:
            if self.is_paused:
                await asyncio.sleep(1)
                continue

            # 1. Aggressive Pruning: Remove closed connections instantly
            self.peers = [p for p in self.peers if not p.closed]

            # 2. Refill the Swarm
            active_count = len(self.peers)
            needed = MAX_ACTIVE_PEERS - active_count

            if needed > 5 and self.all_candidates:  # Only refill if we need at least 5
                random.shuffle(self.all_candidates)
                current_ips = {p.ip for p in self.peers}
                new_batch = []

                for ip, port in self.all_candidates:
                    if ip not in current_ips:
                        new_batch.append((ip, port))
                        if len(new_batch) >= needed:
                            break

                for ip, port in new_batch:
                    peer = PeerConnection(
                        ip, port, self.torrent, self.peer_id,
                        self.piece_manager, self.file_handler
                    )
                    peer.client = self
                    self.peers.append(peer)
                    asyncio.create_task(peer.start())

            # Check faster (Every 2 seconds) to keep speed high
            await asyncio.sleep(2)

        print("DOWNLOAD COMPLETE!")