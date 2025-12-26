from PyQt6.QtCore import QThread, pyqtSignal
from pathlib import Path
import yt_dlp
import time
import json
import hashlib
import urllib.request


class DownloadWorker(QThread):
    finished = pyqtSignal(bool, str)  # success, message
    progress = pyqtSignal(dict)  # progress info dict
    metadata_saved = pyqtSignal(dict)  # emit when metadata is saved

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
        self.metadata_dir = Path(download_dir) / "metadata"

    def run(self):
        try:
            # Create metadata directory if it doesn't exist
            self.metadata_dir.mkdir(exist_ok=True)

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
                'writethumbnail': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(self.url, download=True)

                # Save metadata for each downloaded item
                if info and '_type' in info and info['_type'] == 'playlist':
                    entries = info.get('entries', [])
                    for entry in entries:
                        if entry and 'requested_downloads' in entry:
                            metadata = self.save_metadata(entry)
                            if metadata:
                                self.metadata_saved.emit(metadata)
                elif info:
                    metadata = self.save_metadata(info)
                    if metadata:
                        self.metadata_saved.emit(metadata)

            if self.is_running:
                self.finished.emit(True, "Download completed successfully")
        except Exception as e:
            if self.is_running:
                self.finished.emit(False, f"Download failed: {str(e)}")

    def save_metadata(self, info_dict):
        try:
            video_id = info_dict.get('id', '')
            if not video_id:
                unique_string = f"{info_dict.get('title', '')}{info_dict.get('uploader', '')}"
                video_id = hashlib.md5(unique_string.encode()).hexdigest()[:10]

            metadata = {
                'title': info_dict.get('title'),
                'upload_date': info_dict.get('upload_date'),
                'duration': info_dict.get('duration'),  # in seconds
                'uploader': info_dict.get('uploader'),  # channel name
                'thumbnail': info_dict.get('thumbnail'),
                'view_count': info_dict.get('view_count'),
                'like_count': info_dict.get('like_count'),
                'description': info_dict.get('description'),
                'webpage_url': info_dict.get('webpage_url'),
                'extractor': info_dict.get('extractor'),
                'extractor_key': info_dict.get('extractor_key'),
                'format': self.media_format,
                'download_date': time.strftime('%Y%m%d_%H%M%S'),
                'video_id': video_id,
            }

            if 'requested_downloads' in info_dict and info_dict['requested_downloads']:
                filepath = info_dict['requested_downloads'][0].get('filepath', '')
                if filepath:
                    metadata['filename'] = filepath
                    metadata['filename_short'] = Path(filepath).name

            if metadata['thumbnail']:
                thumbnail_filename = f"{video_id}.jpg"
                thumbnail_path = self.metadata_dir / thumbnail_filename
                try:
                    urllib.request.urlretrieve(metadata['thumbnail'], thumbnail_path)
                    metadata['thumbnail_filename'] = thumbnail_filename
                    metadata['thumbnail_path'] = str(thumbnail_path)
                except Exception as e:
                    print(f"Error downloading thumbnail: {e}")
                    metadata['thumbnail_filename'] = None
                    metadata['thumbnail_path'] = None

            metadata_filename = f"{video_id}.json"
            metadata_path = self.metadata_dir / metadata_filename

            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            print(f"Metadata saved: {metadata_filename}")
            return metadata

        except Exception as e:
            print(f"Error saving metadata: {e}")
            return None

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
        time.sleep(0.1)

    def cleanup(self):
        """Clean up any resources"""
        # Clean up any yt_dlp instances or connections
        pass