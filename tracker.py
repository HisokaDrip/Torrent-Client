import socket
import struct
import random
import requests
from urllib.parse import urlparse
from utils import logger
from ui import ui


class TrackerManager:
    def __init__(self, torrent):
        self.torrent = torrent
        self.peer_id = torrent.peer_id  # We need to pass this in from Client
        self.peers = []  # List of (ip, port)

    def get_peers(self):
        """
        Queries all trackers in the list to find peers.
        Tries UDP first (faster), then HTTP.
        """
        for url in self.torrent.announce_list:
            try:
                if url.startswith("udp"):
                    peers = self._scrape_udp(url)
                elif url.startswith("http"):
                    peers = self._scrape_http(url)
                else:
                    continue

                if peers:
                    ui.print_log(f"Found {len(peers)} peers from {url}", "INFO")
                    self.peers.extend(peers)
            except Exception as e:
                # Trackers often fail/timeout, this is normal
                # ui.print_log(f"Tracker failed {url}: {e}", "WARNING")
                pass

        # Remove duplicates
        self.peers = list(set(self.peers))
        ui.print_log(f"Total Unique Peers: {len(self.peers)}", "INFO")
        return self.peers

    def _scrape_http(self, url):
        """
        Connects to HTTP trackers.
        Requires sending bytes as URL parameters.
        """
        params = {
            'info_hash': self.torrent.info_hash,
            'peer_id': self.peer_id,
            'port': 6881,
            'uploaded': 0,
            'downloaded': 0,
            'left': self.torrent.total_length,
            'compact': 1,
            'event': 'started'
        }
        try:
            response = requests.get(url, params=params, timeout=5)
            # Response is binary. Peers are at the end.
            # (Simplification: Real parsing requires checking bencoded response structure)
            # But most modern trackers return compact binary directly or in 'peers' key
            return self._parse_compact_peers(response.content)
        except:
            return []

    def _scrape_udp(self, url):
        """
        The Hard Part: Implementing BitTorrent UDP Protocol manually.
        Structure:
        1. Connect Request -> 2. Connection ID -> 3. Announce Request -> 4. Peer IPs
        """
        parsed = urlparse(url)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(4)

        try:
            # 1. Connection Request
            connection_id = 0x41727101980  # Magic constant
            action = 0  # 0 = connect
            transaction_id = random.getrandbits(32)

            # Pack struct: (Sign: >QII) = Big-endian, Unsigned Long Long, Int, Int
            packet = struct.pack('>QII', connection_id, action, transaction_id)
            sock.sendto(packet, (parsed.hostname, parsed.port))

            # 2. Receive Connection Response
            response, _ = sock.recvfrom(2048)
            if len(response) < 16:
                return []

            # Unpack: action, transaction_id, connection_id
            res_action, res_trans_id, conn_id = struct.unpack('>IIQ', response[:16])

            if res_action != 0 or res_trans_id != transaction_id:
                return []

            # 3. Announce Request
            action = 1  # 1 = announce
            key = random.getrandbits(32)

            # Complex struct packing for announce
            # info_hash(20), peer_id(20), downloaded(8), left(8), uploaded(8)
            # event(4), ip(4), key(4), num_want(4), port(2)
            packet = struct.pack('>QII', conn_id, action, transaction_id)
            packet += self.torrent.info_hash
            packet += self.peer_id
            packet += struct.pack('>QQQIIIiH', 0, self.torrent.total_length, 0, 2, 0, key, -1, 6881)

            sock.sendto(packet, (parsed.hostname, parsed.port))

            # 4. Receive Peer List
            response, _ = sock.recvfrom(4096)

            # Skip first 20 bytes (action, trans_id, intervals...)
            # Peers start at byte 20. Each peer is 6 bytes (4 byte IP + 2 byte Port)
            return self._parse_compact_peers(response[20:])

        except Exception as e:
            return []
        finally:
            sock.close()

    def _parse_compact_peers(self, data):
        """
        Parses a binary string where every 6 bytes represents an IP:Port.
        """
        peers = []
        # Sometimes http trackers return bencoded dicts, we need to handle raw bytes
        # If data is bytes, try to extract just the peer list if it's mixed
        try:
            offset = 0
            while offset < len(data):
                # We need at least 6 bytes
                if offset + 6 > len(data):
                    break

                ip_bytes = data[offset: offset + 4]
                port_bytes = data[offset + 4: offset + 6]

                # Convert bytes to string IP (e.g., 192.168.1.1)
                ip = socket.inet_ntoa(ip_bytes)
                # Convert bytes to int Port (Big Endian)
                port = struct.unpack('>H', port_bytes)[0]

                peers.append((ip, port))
                offset += 6
        except:
            pass

        return peers