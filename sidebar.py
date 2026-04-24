from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont, QAction
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QToolButton, QFrame,
    QListWidget, QListWidgetItem, QMessageBox, QHBoxLayout,
    QPushButton, QComboBox, QMenu, QInputDialog
)
from pathlib import Path
import json
import os
import sys

if getattr(sys, 'frozen', False):
    # Running as compiled executable
    build_folder = Path(sys.executable).parent
else:
    # Running as normal Python script
    build_folder = Path(__file__).parent


class VideoItemWidget(QWidget):
    add_to_playlist_requested = pyqtSignal(dict)   # video_data
    delete_video_requested = pyqtSignal(dict)      # video_data
    play_clicked = pyqtSignal(dict)                # double-click

    def __init__(self, video_data, parent=None):
        super().__init__(parent)
        self.video_data = video_data

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setFixedSize(60, 40)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background-color: #2d2d2d;
                border: 1px solid #404040;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.thumbnail_label)

        text_widget = QWidget()
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-weight: bold;")
        text_layout.addWidget(self.title_label)

        self.details_label = QLabel()
        self.details_label.setStyleSheet("color: #888888; font-size: 11px;")
        text_layout.addWidget(self.details_label)

        layout.addWidget(text_widget, 1)

        self.menu_button = QToolButton()
        self.menu_button.setIcon(QIcon.fromTheme("application-menu"))
        self.menu_button.setToolTip("Options")
        self.menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.menu_button.setFixedSize(24, 24)
        self.menu_button.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
            }
            QToolButton:hover {
                background-color: #404040;
                border-radius: 3px;
            }
        """)

        self.popup_menu = QMenu(self)
        add_action = QAction("Add to playlist...", self)
        add_action.triggered.connect(self.on_add_to_playlist)
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self.on_delete)
        self.popup_menu.addAction(add_action)
        self.popup_menu.addSeparator()
        self.popup_menu.addAction(delete_action)

        self.menu_button.setMenu(self.popup_menu)
        layout.addWidget(self.menu_button)

        self.setMinimumHeight(50)
        self.update_display()

    def update_display(self):
        title = self.video_data.get('title', 'Unknown Title')
        uploader = self.video_data.get('uploader', 'Unknown Uploader')
        raw_duration = self.video_data.get('duration', 0)

        try:
            duration = int(raw_duration) if raw_duration is not None else 0
        except (TypeError, ValueError):
            duration = 0

        if duration:
            minutes = duration // 60
            seconds = duration % 60
            if minutes > 60:
                hours = minutes // 60
                minutes = minutes % 60
                duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "Unknown"

        self.title_label.setText(title)
        self.details_label.setText(f"{uploader} • {duration_str}")

        thumbnail_filename = self.video_data.get('thumbnail_filename')
        if thumbnail_filename and 'metadata_dir' in self.video_data:
            thumbnail_path = self.video_data['metadata_dir'] / thumbnail_filename
            if thumbnail_path.exists():
                try:
                    pixmap = QPixmap(str(thumbnail_path))
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(60, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation)
                        self.thumbnail_label.setPixmap(pixmap)
                except Exception as e:
                    print(f"Error loading thumbnail {thumbnail_path}: {e}")

    def on_add_to_playlist(self):
        self.add_to_playlist_requested.emit(self.video_data)

    def on_delete(self):
        self.delete_video_requested.emit(self.video_data)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self.video_data)
        super().mouseDoubleClickEvent(event)


class VideoSidebar(QWidget):
    video_selected = pyqtSignal(str)   # video path
    video_deleted = pyqtSignal(str)    # video path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoSidebar")
        self.setFixedWidth(420)

        self.playlists_file = None
        self.playlists = []  # list of {"name": str, "videos": [video_id, ...]}
        self.current_playlist = "All Videos"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        playlist_bar = QWidget()
        playlist_layout = QHBoxLayout(playlist_bar)
        playlist_layout.setContentsMargins(0, 0, 0, 0)
        playlist_layout.setSpacing(5)

        self.playlist_combo = QComboBox()
        self.playlist_combo.addItem("All Videos")
        self.playlist_combo.currentTextChanged.connect(self.on_playlist_changed)

        self.new_playlist_btn = QPushButton("New")
        self.new_playlist_btn.setFixedWidth(40)
        self.new_playlist_btn.setToolTip("Create new playlist")
        self.new_playlist_btn.clicked.connect(self.create_playlist)

        self.del_playlist_btn = QPushButton("Delete")
        self.del_playlist_btn.setFixedWidth(40)
        self.del_playlist_btn.setToolTip("Delete current playlist")
        self.del_playlist_btn.clicked.connect(self.delete_current_playlist)

        playlist_layout.addWidget(self.playlist_combo, 1)
        playlist_layout.addWidget(self.new_playlist_btn)
        playlist_layout.addWidget(self.del_playlist_btn)

        layout.addWidget(playlist_bar)

        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("Video Library")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(11)
        self.title_label.setFont(title_font)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()

        self.refresh_button = QToolButton()
        self.refresh_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_button.setToolTip("Refresh list")
        self.refresh_button.clicked.connect(self.refresh_video_list)
        self.refresh_button.setFixedSize(24, 24)
        header_layout.addWidget(self.refresh_button)

        layout.addWidget(header_widget)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        self.video_list = QListWidget()
        self.video_list.setIconSize(QSize(60, 40))
        self.video_list.setAlternatingRowColors(True)
        self.video_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        layout.addWidget(self.video_list)

        self.info_label = QLabel("No videos found")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: gray; padding: 10px;")
        layout.addWidget(self.info_label)

        self.metadata_dir = None

    def set_metadata_dir(self, metadata_dir):
        self.metadata_dir = Path(metadata_dir)
        self.playlists_file = self.metadata_dir / "playlists.json"
        self.load_playlists()

    # ---------- Playlist management ----------
    def load_playlists(self):
        if not self.playlists_file or not self.playlists_file.exists():
            self.playlists = []
            return
        try:
            with open(self.playlists_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.playlists = data.get("playlists", [])
        except Exception as e:
            print(f"Error loading playlists: {e}")
            self.playlists = []

        self.playlist_combo.blockSignals(True)
        self.playlist_combo.clear()
        self.playlist_combo.addItem("All Videos")
        for pl in self.playlists:
            self.playlist_combo.addItem(pl["name"])
        self.playlist_combo.setCurrentText(self.current_playlist)
        self.playlist_combo.blockSignals(False)

    def save_playlists(self):
        if not self.playlists_file:
            return
        try:
            with open(self.playlists_file, 'w', encoding='utf-8') as f:
                json.dump({"playlists": self.playlists}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving playlists: {e}")

    def create_playlist(self):
        name, ok = QInputDialog.getText(self, "New Playlist", "Playlist name:")
        if ok and name.strip():
            name = name.strip()
            if any(pl["name"] == name for pl in self.playlists):
                QMessageBox.warning(self, "Duplicate", "A playlist with that name already exists.")
                return
            self.playlists.append({"name": name, "videos": []})
            self.save_playlists()
            self.load_playlists()
            self.playlist_combo.setCurrentText(name)
            self.refresh_video_list()

    def delete_current_playlist(self):
        if self.current_playlist == "All Videos":
            QMessageBox.information(self, "Cannot Delete", "The 'All Videos' view cannot be deleted.")
            return
        index = next((i for i, pl in enumerate(self.playlists) if pl["name"] == self.current_playlist), None)
        if index is None:
            return
        reply = QMessageBox.question(self, "Delete Playlist",
                                     f"Delete playlist '{self.current_playlist}'?\nThe videos themselves will NOT be deleted.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            del self.playlists[index]
            self.save_playlists()
            self.current_playlist = "All Videos"
            self.load_playlists()
            self.refresh_video_list()

    def on_playlist_changed(self, name):
        self.current_playlist = name
        self.refresh_video_list()

    def add_video_to_playlist(self, video_data, playlist_name=None):
        video_id = video_data.get("video_id")
        if not video_id:
            QMessageBox.warning(self, "Error", "Cannot identify this video (missing video_id).")
            return

        if playlist_name is None:
            names = [pl["name"] for pl in self.playlists]
            if not names:
                QMessageBox.information(self, "No Playlists", "You have no playlists. Create one first.")
                return
            name, ok = QInputDialog.getItem(self, "Add to Playlist",
                                            "Select playlist:", names, 0, False)
            if not ok or not name:
                return
            playlist_name = name

        for playlist in self.playlists:
            if playlist["name"] == playlist_name:
                if video_id not in playlist["videos"]:
                    playlist["videos"].append(video_id)
                    self.save_playlists()
                else:
                    QMessageBox.information(self, "Already in playlist", f"Video already in '{playlist_name}'")
                break
        if self.current_playlist == playlist_name:
            self.refresh_video_list()

    def remove_video_from_all_playlists(self, video_id):
        changed = False
        for playlist in self.playlists:
            if video_id in playlist["videos"]:
                playlist["videos"].remove(video_id)
                changed = True
        if changed:
            self.save_playlists()
            if self.current_playlist != "All Videos":
                self.refresh_video_list()

    # ---------- Video list refresh and playback ----------
    def refresh_video_list(self):
        self.video_list.clear()

        if not self.metadata_dir or not self.metadata_dir.exists():
            self.info_label.setText("No metadata directory found")
            self.info_label.show()
            return

        metadata_files = list(self.metadata_dir.glob("*.json"))
        metadata_files = [f for f in metadata_files if f.name != "playlists.json"]

        if not metadata_files:
            self.info_label.setText("No videos downloaded yet")
            self.info_label.show()
            return

        self.info_label.hide()

        all_videos = []
        for metadata_file in metadata_files:
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)

                video_path = metadata.get('filename', '')
                if video_path and Path(video_path).exists():
                    video_data = {
                        'video_path': video_path,
                        'metadata_file': str(metadata_file),
                        'title': metadata.get('title', 'Unknown Title'),
                        'uploader': metadata.get('uploader', 'Unknown Uploader'),
                        'duration': metadata.get('duration', 0),
                        'thumbnail_filename': metadata.get('thumbnail_filename'),
                        'metadata_dir': self.metadata_dir,
                        'video_id': metadata.get('video_id', '')
                    }
                    all_videos.append((video_data, metadata))
            except Exception as e:
                print(f"Error loading {metadata_file}: {e}")

        if self.current_playlist != "All Videos":
            playlist = next((pl for pl in self.playlists if pl["name"] == self.current_playlist), None)
            if playlist:
                allowed_ids = set(playlist["videos"])
                all_videos = [v for v in all_videos if v[0].get("video_id") in allowed_ids]

        all_videos.sort(key=lambda x: x[1].get('download_date', ''), reverse=True)

        for video_data, _ in all_videos:
            item_widget = VideoItemWidget(video_data)
            item_widget.play_clicked.connect(self.on_video_play_clicked)          # RESTORED
            item_widget.add_to_playlist_requested.connect(self.on_add_to_playlist_requested)
            item_widget.delete_video_requested.connect(self.delete_video_dialog)

            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())
            self.video_list.addItem(item)
            self.video_list.setItemWidget(item, item_widget)

        if self.video_list.count() == 0:
            self.info_label.setText("No videos in this playlist")
            self.info_label.show()

    def on_video_play_clicked(self, video_data):
        video_path = video_data.get('video_path')
        if video_path:
            self.video_selected.emit(video_path)

    def on_add_to_playlist_requested(self, video_data):
        self.add_video_to_playlist(video_data)

    def delete_video_dialog(self, video_data):
        video_path = video_data.get('video_path', '')
        metadata_file = video_data.get('metadata_file', '')
        title = video_data.get('title', 'Unknown Video')
        video_id = video_data.get('video_id', '')

        if not video_path or not metadata_file:
            return

        reply = QMessageBox.question(
            self,
            "Delete Video",
            f"Are you sure you want to delete '{title}'?\n\nThis will delete:\n• The video file\n• Metadata file\n• Thumbnail image\n• Remove from all playlists\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.delete_video(video_data, video_id)

    def delete_video(self, video_data, video_id):
        video_path = video_data.get('video_path', '')
        metadata_file = video_data.get('metadata_file', '')
        thumbnail_filename = video_data.get('thumbnail_filename')
        metadata_dir = video_data.get('metadata_dir')

        if not video_path or not metadata_file:
            return

        try:
            files_deleted = []
            files_failed = []

            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                    files_deleted.append(f"Video file: {Path(video_path).name}")
                except Exception as e:
                    files_failed.append(f"Video file: {str(e)}")

            if os.path.exists(metadata_file):
                try:
                    os.remove(metadata_file)
                    files_deleted.append(f"Metadata file: {Path(metadata_file).name}")
                except Exception as e:
                    files_failed.append(f"Metadata file: {str(e)}")

            if thumbnail_filename and metadata_dir:
                thumbnail_path = metadata_dir / thumbnail_filename
                if thumbnail_path.exists():
                    try:
                        os.remove(thumbnail_path)
                        files_deleted.append(f"Thumbnail: {thumbnail_filename}")
                    except Exception as e:
                        files_failed.append(f"Thumbnail: {str(e)}")

            if video_id:
                self.remove_video_from_all_playlists(video_id)

            if files_failed:
                error_msg = "Some files could not be deleted:\n" + "\n".join(files_failed)
                QMessageBox.warning(self, "Deletion Warning", error_msg)

            self.video_deleted.emit(video_path)
            self.refresh_video_list()
        except Exception as e:
            QMessageBox.critical(self, "Deletion Error", f"Error deleting video: {str(e)}")


class RightSidebar(QWidget):
    chapter_selected = pyqtSignal(float)  # emits start time in seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RightSidebar")
        self.setFixedWidth(50)  # collapsed width
        self._expanded = False
        self._expanded_width = 300
        self._collapsed_width = 50

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toggle button (icon only)
        self.toggle_button = QPushButton()
        self.toggle_button.setIcon(QIcon(os.path.join(build_folder, "chapters.png")))
        self.toggle_button.setToolTip("Show/Hide Chapters")
        self.toggle_button.setFixedSize(40, 40)
        self.toggle_button.clicked.connect(self.toggle_expand)
        layout.addWidget(self.toggle_button, alignment=Qt.AlignmentFlag.AlignTop)

        # Container for chapters (hidden when collapsed)
        self.chapters_container = QWidget()
        self.chapters_layout = QVBoxLayout(self.chapters_container)
        self.chapters_layout.setContentsMargins(5, 10, 5, 10)
        self.chapters_layout.setSpacing(5)

        self.chapters_list = QListWidget()
        self.chapters_list.setAlternatingRowColors(True)
        self.chapters_list.itemClicked.connect(self.on_chapter_clicked)
        self.chapters_layout.addWidget(self.chapters_list)

        self.no_chapters_label = QLabel("No chapters available")
        self.no_chapters_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_chapters_label.setWordWrap(True)
        self.no_chapters_label.hide()
        self.chapters_layout.addWidget(self.no_chapters_label)

        layout.addWidget(self.chapters_container)
        self.chapters_container.hide()  # start collapsed

        self.current_metadata = None

    def toggle_expand(self):
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        self.setFixedWidth(self._expanded_width)
        self.chapters_container.show()
        self._expanded = True

    def collapse(self):
        self.setFixedWidth(self._collapsed_width)
        self.chapters_container.hide()
        self._expanded = False

    def set_chapters(self, metadata):
        self.current_metadata = metadata
        if metadata is None:
            self.clear_chapters()
            return

        chapters = metadata.get('chapters', [])
        if not isinstance(chapters, list):
            chapters = []

        self.chapters_list.clear()
        if chapters:
            try:
                for ch in chapters:
                    if not isinstance(ch, dict):
                        continue
                    title = ch.get('title', 'Chapter')
                    start = ch.get('start', 0)
                    try:
                        start = float(start)
                    except (TypeError, ValueError):
                        start = 0

                    total_seconds = int(start)
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    seconds = total_seconds % 60
                    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    item_text = f"{time_str} - {title}"
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, start)
                    self.chapters_list.addItem(item)
                self.no_chapters_label.hide()
                self.chapters_list.show()
            except Exception as e:
                print(f"Error loading chapters: {e}")
                self.no_chapters_label.setText("Error loading chapters")
                self.no_chapters_label.show()
                self.chapters_list.hide()
        else:
            self.no_chapters_label.show()
            self.chapters_list.hide()

    def on_chapter_clicked(self, item):
        chapter_time = item.data(Qt.ItemDataRole.UserRole)
        if chapter_time is not None:
            self.chapter_selected.emit(float(chapter_time))

    def clear_chapters(self):
        self.chapters_list.clear()
        self.no_chapters_label.hide()
        self.current_metadata = None