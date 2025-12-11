import os
from utils import logger


class FileHandler:
    def __init__(self, torrent, save_path):
        self.torrent = torrent
        self.save_path = save_path  # Now we store the user's chosen folder
        self.descriptors = []
        self._open_files()

    def _open_files(self):
        """Opens all files in the torrent for binary writing."""
        # Use the path the user selected + Torrent Name folder
        base_dir = os.path.join(self.save_path, self.torrent.name)
        os.makedirs(base_dir, exist_ok=True)

        current_offset = 0
        self.files_info = []

        for f in self.torrent.files:
            # Handle subfolders in multi-file torrents (replace backslashes for Windows)
            safe_path = f['path'].replace('\\', '/')
            full_path = os.path.join(base_dir, safe_path)

            # Ensure subdirectories exist
            os.makedirs(os.path.dirname(full_path), exist_ok=True)

            # Create empty sparse files (Reserve space on disk)
            if not os.path.exists(full_path):
                with open(full_path, 'wb') as new_f:
                    new_f.seek(f['length'] - 1)
                    new_f.write(b'\0')

            # Open in Read/Write Binary mode
            fd = open(full_path, 'rb+')
            self.files_info.append({
                "fd": fd,
                "start": current_offset,
                "end": current_offset + f['length'],
                "path": full_path
            })
            current_offset += f['length']

    def write(self, piece_index, data):
        """Writes a downloaded piece to the correct location on disk."""
        piece_start = piece_index * self.torrent.piece_length
        piece_end = piece_start + len(data)

        for f in self.files_info:
            # Check if this file overlaps with the piece data
            if piece_end <= f["start"] or piece_start >= f["end"]:
                continue

            # Calculate where to write in the file
            write_start = max(piece_start, f["start"])
            write_end = min(piece_end, f["end"])
            write_len = write_end - write_start

            file_seek_pos = write_start - f["start"]
            data_read_pos = write_start - piece_start

            f["fd"].seek(file_seek_pos)
            f["fd"].write(data[data_read_pos: data_read_pos + write_len])

    def close(self):
        for f in self.files_info:
            f["fd"].close()