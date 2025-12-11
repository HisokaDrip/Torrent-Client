import math
import random
from utils import Bitfield, logger


class PieceManager:
    def __init__(self, torrent):
        self.torrent = torrent
        self.bitfield = Bitfield(torrent.number_of_pieces)

        # 1. Populate the list of needed pieces
        self.missing_pieces = list(range(torrent.number_of_pieces))

        # 2. FIX: Randomize immediately!
        # This prevents the "Piece 0, 1, 2" linear bottleneck.
        random.shuffle(self.missing_pieces)

        self.ongoing_pieces = []
        self.total_pieces = torrent.number_of_pieces

    def get_next_piece_index(self):
        """
        Retrieves the next piece index.
        Note: The heavy lifting is done in peer.py which reads this list.
        """
        # Prioritize missing pieces
        if self.missing_pieces:
            return self.missing_pieces[0]

        # Endgame: If no missing pieces, return an ongoing one (Double Download)
        if self.ongoing_pieces:
            return random.choice(self.ongoing_pieces)

        return None

    def mark_piece_complete(self, index):
        if index in self.ongoing_pieces:
            self.ongoing_pieces.remove(index)

        if index in self.missing_pieces:
            self.missing_pieces.remove(index)

        self.bitfield.set_piece(index)
        # We don't log every piece to save performance in high-speed mode

    def mark_piece_failed(self, index):
        """If a piece fails hash check, put it back and SHUFFLE."""
        if index in self.ongoing_pieces:
            self.ongoing_pieces.remove(index)

        if index not in self.missing_pieces:
            self.missing_pieces.append(index)
            # Shuffle again so we don't try the same failed piece immediately
            random.shuffle(self.missing_pieces)

    @property
    def complete(self):
        return len(self.missing_pieces) == 0 and len(self.ongoing_pieces) == 0

    @property
    def is_endgame(self):
        """
        Returns True if we are in the last 5% of the download.
        This tells peers to start 'Racing' (Double Downloading).
        """
        remaining = len(self.missing_pieces)
        total = self.total_pieces
        # Trigger endgame if less than 5% left or less than 20 pieces total
        return (remaining < 20) or (remaining / total < 0.05)