from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import yt_dlp

class DownloadWorker(QThread):
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str)

    def __init__(self, url: str, download_dir: str):
        super().__init__()
        self.url = url
        self.download_dir = download_dir

    def run(self):
        try:
            ydl_opts = {
                'outtmpl': str(Path(self.download_dir) / '%(title)s.%(ext)s'),
                'format': "bv*[vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/b",
                'postprocessors': [],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished.emit(True, "Download completed successfully")
        except Exception as e:
            self.finished.emit(False, f"Download failed: {str(e)}")