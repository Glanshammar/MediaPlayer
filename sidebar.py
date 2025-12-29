from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QToolButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QHBoxLayout,
    QPushButton
)
from pathlib import Path
import json
import os

class VideoItemWidget(QWidget):
    delete_clicked = pyqtSignal(dict)  # Signal emitted when delete button is clicked
    play_clicked = pyqtSignal(dict)  # Signal emitted when item is clicked (for playing)

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

        layout.addWidget(text_widget, 1)  # 1 = stretch factor

        self.delete_button = QPushButton()
        self.delete_button.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_button.setFixedSize(24, 24)
        self.delete_button.setToolTip("Delete video")
        self.delete_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #ff4444;
                border-radius: 3px;
            }
            QPushButton:pressed {
                background-color: #cc3333;
            }
        """)
        self.delete_button.clicked.connect(self.on_delete_clicked)
        layout.addWidget(self.delete_button)
        self.setMinimumHeight(50)
        self.update_display()

    def update_display(self):
        title = self.video_data.get('title', 'Unknown Title')
        uploader = self.video_data.get('uploader', 'Unknown Uploader')
        duration = self.video_data.get('duration', 0)

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

    def on_delete_clicked(self):
        self.delete_clicked.emit(self.video_data)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.play_clicked.emit(self.video_data)
        super().mouseDoubleClickEvent(event)


class VideoSidebar(QWidget):
    video_selected = pyqtSignal(str)
    video_deleted = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoSidebar")
        self.setFixedWidth(420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

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

    def refresh_video_list(self):
        self.video_list.clear()

        if not self.metadata_dir or not self.metadata_dir.exists():
            self.info_label.setText("No metadata directory found")
            self.info_label.show()
            return

        metadata_files = list(self.metadata_dir.glob("*.json"))

        if not metadata_files:
            self.info_label.setText("No videos downloaded yet")
            self.info_label.show()
            return

        self.info_label.hide()

        videos_info = []
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
                        'metadata_dir': self.metadata_dir
                    }

                    videos_info.append({
                        'video_data': video_data,
                        'metadata': metadata
                    })
            except Exception as e:
                print(f"Error loading metadata {metadata_file}: {e}")

        videos_info.sort(key=lambda x: x['metadata'].get('download_date', ''), reverse=True)

        for video_info in videos_info:
            video_data = video_info['video_data']

            item_widget = VideoItemWidget(video_data)
            item_widget.delete_clicked.connect(self.delete_video_dialog)
            item_widget.play_clicked.connect(self.on_video_play_clicked)

            item = QListWidgetItem()
            item.setSizeHint(item_widget.sizeHint())

            self.video_list.addItem(item)
            self.video_list.setItemWidget(item, item_widget)

    def on_video_play_clicked(self, video_data):
        video_path = video_data.get('video_path')
        if video_path:
            self.video_selected.emit(video_path)

    def delete_video_dialog(self, video_data):
        video_path = video_data.get('video_path', '')
        metadata_file = video_data.get('metadata_file', '')
        title = video_data.get('title', 'Unknown Video')

        if not video_path or not metadata_file:
            return

        reply = QMessageBox.question(
            self,
            "Delete Video",
            f"Are you sure you want to delete '{title}'?\n\nThis will delete:\n• The video file\n• Metadata file\n• Thumbnail image\n\nThis action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        self.delete_video(video_data)

    def delete_video(self, video_data):
        video_path = video_data.get('video_path', '')
        metadata_file = video_data.get('metadata_file', '')
        title = video_data.get('title', 'Unknown Video')
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

            if files_failed:
                error_msg = "Some files could not be deleted:\n"
                error_msg += "\n".join(files_failed)
                QMessageBox.warning(self, "Deletion Warning", error_msg)
            else:
                success_msg = f"'{title}' deleted successfully.\n\nDeleted files:\n"
                success_msg += "\n".join(files_deleted)
                QMessageBox.information(self, "Video Deleted", success_msg)

            self.video_deleted.emit(video_path)
            self.refresh_video_list()

        except Exception as e:
            QMessageBox.critical(self, "Deletion Error",
                                 f"Error deleting video: {str(e)}")