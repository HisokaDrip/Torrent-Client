import random
import string
import hashlib
import logging

# Configure logging to look professional
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("FluxTorrent")

def generate_peer_id():
    """
    Generates a unique 20-byte ID for our client.
    Format: -FX0001- + 12 random alphanumeric characters.
    """
    client_id = '-FX0001-'
    random_chars = ''.join(
        random.choice(string.ascii_letters + string.digits) 
        for _ in range(12)
    )
    return (client_id + random_chars).encode('utf-8')

def sha1_hash(data: bytes) -> bytes:
    """Computes the SHA-1 hash of the given binary data."""
    return hashlib.sha1(data).digest()

class Bitfield:
    """
    Efficiently tracks which pieces a peer has using a bit array.
    This is highly optimized for memory.
    """
    def __init__(self, size):
        self.size = size
        # Calculate number of bytes needed (ceiling division)
        self.field = bytearray((size + 7) // 8)

    def set_piece(self, index):
        """Mark piece at 'index' as possessed."""
        byte_index = index // 8
        bit_index = 7 - (index % 8)
        self.field[byte_index] |= (1 << bit_index)

    def has_piece(self, index):
        """Check if we have the piece at 'index'."""
        byte_index = index // 8
        bit_index = 7 - (index % 8)
        return (self.field[byte_index] >> bit_index) & 1