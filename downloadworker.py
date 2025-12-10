from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import yt_dlp
import time


class DownloadWorker(QThread):
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(dict)  # progress info dict

    def __init__(self, url: str, download_dir: str, media_format: str):
        super().__init__()
        self.url = url
        self.download_dir = download_dir
        self.media_format = media_format
        self.total_videos = 1
        self.current_video = 1
        self.current_title = ""
        self.last_progress_time = 0
        self.last_percent = 0
        self.is_running = True

    def run(self):
        try:
            if self.media_format == "video":
                format_opts = "bv*[vcodec^=avc1]+ba[ext=m4a]/b[ext=mp4]/b"
            elif self.media_format == "audio":
                format_opts = "bestaudio[ext=m4a]/bestaudio/best"
            else:
                format_opts = "best"

            ydl_info_opts = {
                'quiet': True,
                'extract_flat': True,
                'ignoreerrors': True,
            }

            with yt_dlp.YoutubeDL(ydl_info_opts) as ydl:
                info = ydl.extract_info(self.url, download=False)

                if info and '_type' in info and info['_type'] == 'playlist':
                    self.total_videos = len(info.get('entries', []))
                    self.progress.emit({
                        'type': 'playlist_info',
                        'total': self.total_videos,
                        'title': info.get('title', 'Playlist'),
                        'message': f"Found {self.total_videos} videos in playlist"
                    })
                else:
                    self.total_videos = 1
                    if info and 'title' in info:
                        self.current_title = info['title']
                        self.progress.emit({
                            'type': 'video_info',
                            'title': self.current_title,
                            'message': f"Found: {self.current_title}"
                        })

            def progress_hook(d):
                self.process_progress_hook(d)

            ydl_opts = {
                'outtmpl': str(Path(self.download_dir) / '%(title)s.%(ext)s'),
                'format': format_opts,
                'postprocessors': [],
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
                'ignoreerrors': True,
                'extract_flat': False,
                'noprogress': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])

            if self.is_running:
                self.finished.emit(True, "Download completed successfully")
        except Exception as e:
            if self.is_running:
                self.finished.emit(False, f"Download failed: {str(e)}")

    def process_progress_hook(self, d):
        if not self.is_running:
            return

        try:
            current_time = time.time()

            if current_time - self.last_progress_time < 0.1:
                return

            self.last_progress_time = current_time

            status = d.get('status', '')

            if status == 'downloading':
                if 'info_dict' in d:
                    info = d['info_dict']
                    self.current_title = info.get('title', self.current_title)
                    self.current_video = info.get('playlist_index', self.current_video)

                # Calculate percentage
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded_bytes = d.get('downloaded_bytes', 0)

                if total_bytes and total_bytes > 0:
                    percent = (downloaded_bytes / total_bytes) * 100
                else:
                    percent_str = d.get('_percent_str', '0%')
                    try:
                        percent = float(percent_str.strip('%'))
                    except ValueError:
                        percent = 0

                # Only emit if percentage changed significantly (to avoid too many signals)
                if abs(percent - self.last_percent) < 0.5 and percent < 100:
                    return

                self.last_percent = percent
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')

                display_title = self.current_title
                if len(display_title) > 30:
                    display_title = display_title[:27] + "..."

                self.progress.emit({
                    'type': 'progress',
                    'status': 'downloading',
                    'title': display_title,
                    'full_title': self.current_title,
                    'current': self.current_video,
                    'total': self.total_videos,
                    'percent': percent,
                    'speed': speed,
                    'eta': eta,
                    'message': f"Downloading {display_title}"
                })

            elif status == 'finished':
                title = d.get('info_dict', {}).get('title', self.current_title)
                self.progress.emit({
                    'type': 'finished_video',
                    'status': 'finished',
                    'title': title,
                    'current': self.current_video,
                    'total': self.total_videos,
                    'message': f"Finished: {title}"
                })

            elif status == 'error':
                self.progress.emit({
                    'type': 'error',
                    'status': 'error',
                    'message': d.get('error', 'Unknown error'),
                })
        except Exception as e:
            print(f"Progress hook error: {e}")

    def stop(self):
        self.is_running = False