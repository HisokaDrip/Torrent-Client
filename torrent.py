import math
from bencoding import Decoder, Encoder
from utils import sha1_hash, logger

class Torrent:
    def __init__(self, file_path):
        self.file_path = file_path
        self.meta_info = self._load_meta_info()
        
        # 1. Extract Announce URL (The Tracker)
        self.announce = self.meta_info['announce'].decode('utf-8')
        self.announce_list = self._get_announce_list()
        
        # 2. Extract Info Dictionary
        self.info = self.meta_info['info']
        self.name = self.info['name'].decode('utf-8')
        self.piece_length = self.info['piece length']
        
        # 3. Calculate Info Hash (This is the unique ID of the torrent)
        raw_info = Encoder.encode(self.info)
        self.info_hash = sha1_hash(raw_info)
        
        # 4. Handle Files (Single vs Multi-file)
        self.files = self._parse_files()
        self.total_length = sum(f['length'] for f in self.files)
        
        # 5. Parse Piece Hashes
        self.pieces_hashes = self._parse_pieces_hashes()
        self.number_of_pieces = len(self.pieces_hashes)
        
        logger.info(f"Loaded Torrent: {self.name}")
        logger.info(f"Size: {self.total_length / (1024*1024):.2f} MB")
        logger.info(f"Pieces: {self.number_of_pieces} (Length: {self.piece_length})")
        logger.info(f"Info Hash: {self.info_hash.hex()}")

    def _load_meta_info(self):
        with open(self.file_path, 'rb') as f:
            data = f.read()
            return Decoder(data).decode()

    def _get_announce_list(self):
        """Returns a list of all tracker URLs."""
        trackers = []
        if 'announce-list' in self.meta_info:
            for tier in self.meta_info['announce-list']:
                for url in tier:
                    trackers.append(url.decode('utf-8'))
        elif 'announce' in self.meta_info:
            trackers.append(self.meta_info['announce'].decode('utf-8'))
        return trackers

    def _parse_files(self):
        files = []
        if 'files' in self.info:
            # Multi-file mode
            for f in self.info['files']:
                path = '/'.join([p.decode('utf-8') for p in f['path']])
                files.append({'length': f['length'], 'path': path})
        else:
            # Single-file mode
            files.append({'length': self.info['length'], 'path': self.name})
        return files

    def _parse_pieces_hashes(self):
        """
        The 'pieces' string is a concatenation of 20-byte SHA1 hashes.
        We split it into a list.
        """
        pieces = self.info['pieces']
        if len(pieces) % 20 != 0:
            raise ValueError("Invalid piece hash length")
        
        hash_list = []
        for i in range(0, len(pieces), 20):
            hash_list.append(pieces[i : i + 20])
        return hash_list