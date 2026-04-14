import sys
import os
from pathlib import Path

# Force Qt to use XCB platform if running on Linux with Wayland
if sys.platform.startswith('linux'):
    wayland_display = os.environ.get('WAYLAND_DISPLAY')
    if wayland_display and os.environ.get('QT_QPA_PLATFORM') != 'xcb':
            print("Wayland detected – forcing Qt platform to xcb for VLC embedding")
            os.environ['QT_QPA_PLATFORM'] = 'xcb'

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from mediaplayer import MediaPlayer

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle('Fusion')

        # --- Windows: set App User Model ID (needed for taskbar icon) ---
        if sys.platform == 'win32':
            import ctypes
            myappid = 'glanshammar.mediaplayer'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        # Detect if running as PyInstaller bundle
        if getattr(sys, 'frozen', False):
            bundle_dir = Path(sys._MEIPASS)
        else:
            bundle_dir = Path(__file__).parent

        icon_path = bundle_dir / 'app_icon.png'
        app.setWindowIcon(QIcon(str(icon_path)))

        player = MediaPlayer()
        player.show()

        sys.exit(app.exec())
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)