from collections import OrderedDict

class Decoder:
    """
    Decodes Bencoded data (d, l, i, s) used in torrent files.
    Uses a recursive descent parser.
    """
    def __init__(self, data: bytes):
        self._data = data
        self._index = 0

    def decode(self):
        """Main entry point for decoding."""
        if self._index >= len(self._data):
            return None
            
        char = chr(self._data[self._index])

        if char == 'i':
            return self._decode_int()
        elif char == 'l':
            return self._decode_list()
        elif char == 'd':
            return self._decode_dict()
        elif char.isdigit():
            return self._decode_string()
        else:
            raise ValueError(f"Invalid bencoding at index {self._index}")

    def _decode_int(self):
        self._index += 1  # Skip 'i'
        end = self._data.find(b'e', self._index)
        if end == -1:
            raise ValueError("Invalid integer format")
        
        number = int(self._data[self._index:end])
        self._index = end + 1  # Skip 'e'
        return number

    def _decode_string(self):
        colon = self._data.find(b':', self._index)
        if colon == -1:
            raise ValueError("Invalid string format")
        
        length = int(self._data[self._index:colon])
        self._index = colon + 1
        
        s = self._data[self._index : self._index + length]
        self._index += length
        return s

    def _decode_list(self):
        self._index += 1  # Skip 'l'
        lst = []
        while chr(self._data[self._index]) != 'e':
            lst.append(self.decode())
        self._index += 1  # Skip 'e'
        return lst

    def _decode_dict(self):
        self._index += 1  # Skip 'd'
        d = OrderedDict()
        while chr(self._data[self._index]) != 'e':
            key = self.decode()
            if not isinstance(key, bytes):
                # Keys in bencoded dicts must be strings (bytes)
                raise ValueError("Dict keys must be strings")
            val = self.decode()
            d[key.decode('utf-8')] = val
        self._index += 1  # Skip 'e'
        return d

class Encoder:
    """Encodes Python objects back into Bencoded bytes."""
    @staticmethod
    def encode(data):
        if isinstance(data, str):
            return Encoder.encode(data.encode('utf-8'))
        elif isinstance(data, int):
            return f"i{data}e".encode()
        elif isinstance(data, bytes):
            return f"{len(data)}:".encode() + data
        elif isinstance(data, list):
            encoded = b"l" + b"".join([Encoder.encode(item) for item in data]) + b"e"
            return encoded
        elif isinstance(data, dict) or isinstance(data, OrderedDict):
            encoded = b"d"
            # Bencoding requires dict keys to be sorted lexicographically
            for k, v in sorted(data.items()):
                encoded += Encoder.encode(k) + Encoder.encode(v)
            encoded += b"e"
            return encoded
        else:
            raise TypeError(f"Cannot encode type: {type(data)}")