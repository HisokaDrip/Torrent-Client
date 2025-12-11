import asyncio
import struct
import time
import random
from utils import logger, sha1_hash

BLOCK_SIZE = 16384  # 16KB


class PeerConnection:
    def __init__(self, ip, port, torrent, peer_id, piece_manager, file_handler):
        self.ip = ip
        self.port = port
        self.torrent = torrent
        self.my_peer_id = peer_id
        self.piece_manager = piece_manager
        self.file_handler = file_handler

        self.reader = None
        self.writer = None
        self.peer_choking = True
        self.am_interested = False

        self.peer_pieces = [False] * torrent.number_of_pieces
        self.current_piece_index = None
        self.current_piece_buffer = {}
        self.request_pending = False
        self.last_activity = time.time()

        self.client = None
        self.closed = False

    async def start(self):
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port, limit=2 ** 18),
                timeout=5
            )
            await self._perform_handshake()
            await self._message_loop()
        except Exception:
            pass
        finally:
            self.close()

    async def _perform_handshake(self):
        pstr = b"BitTorrent protocol"
        handshake = struct.pack(
            f'>B{len(pstr)}s8s20s20s',
            len(pstr), pstr, b'\x00' * 8, self.torrent.info_hash, self.my_peer_id
        )
        self.writer.write(handshake)
        await self.writer.drain()

        await self.reader.readexactly(68)
        await self._send_message(2)
        self.am_interested = True

    async def _message_loop(self):
        while True:
            try:
                length_data = await asyncio.wait_for(self.reader.readexactly(4), timeout=15)
            except:
                return

            length = struct.unpack('>I', length_data)[0]
            if length == 0: continue

            msg_id = ord(await self.reader.readexactly(1))

            payload = b""
            if length > 1:
                payload = await self.reader.readexactly(length - 1)

            self.last_activity = time.time()
            await self._handle_message(msg_id, payload)

    async def _handle_message(self, msg_id, payload):
        if msg_id == 0:  # Choke
            self.peer_choking = True
        elif msg_id == 1:  # Unchoke
            self.peer_choking = False
            await self._request_piece()

        elif msg_id == 4:  # Have
            piece_index = struct.unpack('>I', payload)[0]
            if piece_index < len(self.peer_pieces):
                self.peer_pieces[piece_index] = True

        elif msg_id == 5:  # Bitfield
            byte_index = 0
            bit_index = 0
            for i in range(len(self.peer_pieces)):
                if byte_index < len(payload):
                    if (payload[byte_index] >> (7 - bit_index)) & 1:
                        self.peer_pieces[i] = True
                    bit_index += 1
                    if bit_index == 8:
                        bit_index = 0
                        byte_index += 1
            if not self.peer_choking:
                await self._request_piece()

        elif msg_id == 7:  # Piece Data
            await self._handle_block(payload)

    def _get_valid_piece_index(self):
        """
        SMART SELECTION LOGIC:
        1. Check Missing Pieces (Random Order).
        2. Check Endgame (Double Download).
        """
        # 1. Standard: Find a missing piece that no one else is doing
        for piece_idx in self.piece_manager.missing_pieces:
            if self.peer_pieces[piece_idx]:
                if piece_idx not in self.piece_manager.ongoing_pieces:
                    self.piece_manager.ongoing_pieces.append(piece_idx)
                    return piece_idx

        # 2. ENDGAME: If we found nothing above, AND we are in endgame mode...
        if self.piece_manager.is_endgame:
            # Look at what OTHER peers are downloading right now
            candidates = [p for p in self.piece_manager.ongoing_pieces if self.peer_pieces[p]]
            if candidates:
                # Pick one and help them finish it! (Race Condition)
                return random.choice(candidates)

        return None

    async def _request_piece(self):
        if hasattr(self, 'client') and self.client and self.client.is_paused:
            return

        if self.peer_choking or self.request_pending: return

        index = self._get_valid_piece_index()
        if index is None: return

        self.current_piece_index = index
        self.current_piece_buffer = {}
        self.request_pending = True

        piece_length = self.torrent.piece_length
        if index == self.torrent.number_of_pieces - 1:
            remainder = self.torrent.total_length % self.torrent.piece_length
            if remainder: piece_length = remainder

        # Zero-Wait Pipelining
        buffer_reqs = b""
        for begin in range(0, piece_length, BLOCK_SIZE):
            length = min(BLOCK_SIZE, piece_length - begin)
            req_header = struct.pack('>IBIII', 13, 6, index, begin, length)
            buffer_reqs += req_header

        self.writer.write(buffer_reqs)

    async def _handle_block(self, payload):
        try:
            index, begin = struct.unpack('>II', payload[:8])
            block_data = payload[8:]

            if index != self.current_piece_index: return

            self.current_piece_buffer[begin] = block_data

            piece_length = self.torrent.piece_length
            if index == self.torrent.number_of_pieces - 1:
                remainder = self.torrent.total_length % self.torrent.piece_length
                if remainder: piece_length = remainder

            current_size = sum(len(b) for b in self.current_piece_buffer.values())

            if current_size == piece_length:
                self._verify_and_write(index)
                self.request_pending = False
                await self._request_piece()
        except:
            self.request_pending = False

    def _verify_and_write(self, index):
        data = b"".join(
            self.current_piece_buffer[begin]
            for begin in sorted(self.current_piece_buffer.keys())
        )
        expected_hash = self.torrent.pieces_hashes[index]
        if sha1_hash(data) == expected_hash:
            self.file_handler.write(index, data)
            self.piece_manager.mark_piece_complete(index)
        else:
            self.piece_manager.mark_piece_failed(index)

    async def _send_message(self, msg_id, payload=b''):
        length = 1 + len(payload)
        header = struct.pack('>IB', length, msg_id)
        self.writer.write(header + payload)
        await self.writer.drain()

    def close(self):
        self.closed = True
        if self.writer:
            try:
                self.writer.close()
            except:
                pass