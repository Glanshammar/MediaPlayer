import sys
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