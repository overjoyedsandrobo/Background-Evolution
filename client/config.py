import os

BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "http://127.0.0.1:8000")
BACKEND_REQUEST_TIMEOUT_SECONDS = 2.0

WINDOW_W, WINDOW_H = 300, 600
RESOLUTION_SCALE = 4
ASPECT_RATIO = WINDOW_W / WINDOW_H
FPS = 240
NUM_SAVE_SLOTS = 3
AUTOSAVE_INTERVAL_SECONDS = 1.0

# Resolve assets relative to this file's directory, not the process's
# current working directory, so `python client/main.py` works the same
# regardless of where it's launched from.
CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(CLIENT_DIR, "assets")

START_MENU_BACKGROUND_PATH = os.path.join(ASSETS_DIR, "icons", "background", "start_menu.png")
PETAWARU_IMAGE_PATH = os.path.join(ASSETS_DIR, "icons", "monster", "petawaru.png")

# Must match backend/app/progression.py's FIRST_CYCLE_THRESHOLD_SECONDS_TEST.
# The server is authoritative on whether the threshold has actually been
# crossed; this local copy is only used to render the progress bar/label.
HIDDEN_UNLOCK_THRESHOLD_SECONDS_TEST = 10.0

DEFAULT_ENVIRONMENT_KEYS = ["water", "earth", "air", "fire"]
