import sys
import os

# Force Qt to use XCB platform if running on Linux with Wayland
if sys.platform.startswith('linux'):
    wayland_display = os.environ.get('WAYLAND_DISPLAY')
    if wayland_display:
        if os.environ.get('QT_QPA_PLATFORM') != 'xcb':
            print("Wayland detected – forcing Qt platform to xcb for VLC embedding")
            os.environ['QT_QPA_PLATFORM'] = 'xcb'

from PyQt6.QtWidgets import QApplication
from mediaplayer import MediaPlayer

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        player = MediaPlayer()
        player.show()

        sys.exit(app.exec())
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)