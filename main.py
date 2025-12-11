import logging
# Silence noisy libraries so the terminal stays clean
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

# IMPORT THE NEW CLASS NAME HERE
from gui import FluxAnimeGUI

if __name__ == "__main__":
    # Initialize the Ultimate Anime Interface
    app = FluxAnimeGUI()
    app.mainloop()