from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import yt_dlp

class DownloadWorker(QThread):
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(str)

    def __init__(self, url: str, download_dir: str, media_format: str):
        super().__init__()
        self.url = url
        self.download_dir = download_dir
        self.media_format = media_format

    def run(self, media_format="video"):
        try:
            if self.media_format == "video":
                self.format_opts = "bv*[vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/b"
            elif self.media_format == "audio":
                self.format_opts = "bestaudio[ext=m4a]/bestaudio/best"
            ydl_opts = {
                'outtmpl': str(Path(self.download_dir) / '%(title)s.%(ext)s'),
                'format': self.format_opts,
                'postprocessors': [],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self.finished.emit(True, "Download completed successfully")
        except Exception as e:
            self.finished.emit(False, f"Download failed: {str(e)}")