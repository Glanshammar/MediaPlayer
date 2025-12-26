from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QPixmap, QFont
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QFrame,
    QListWidget,
    QListWidgetItem,
)
from pathlib import Path
import json

class VideoSidebar(QWidget):
    video_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VideoSidebar")
        self.setFixedWidth(300)

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
        self.video_list.itemDoubleClicked.connect(self.on_video_double_clicked)
        self.video_list.setAlternatingRowColors(True)
        layout.addWidget(self.video_list)

        self.info_label = QLabel("No videos found")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: gray; padding: 10px;")
        layout.addWidget(self.info_label)

        self.video_data = {}
        self.metadata_dir = None

    def set_metadata_dir(self, metadata_dir):
        self.metadata_dir = Path(metadata_dir)

    def refresh_video_list(self):
        self.video_list.clear()
        self.video_data.clear()

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
                    videos_info.append({
                        'metadata': metadata,
                        'metadata_file': metadata_file,
                        'video_path': video_path
                    })
            except Exception as e:
                print(f"Error loading metadata {metadata_file}: {e}")

        videos_info.sort(key=lambda x: x['metadata'].get('download_date', ''), reverse=True)

        # Add videos to list
        for video_info in videos_info:
            metadata = video_info['metadata']
            video_path = video_info['video_path']
            item = QListWidgetItem()
            title = metadata.get('title', 'Unknown Title')
            uploader = metadata.get('uploader', 'Unknown Uploader')
            duration = metadata.get('duration', 0)

            if duration:
                minutes = duration // 60
                seconds = duration % 60
                duration_str = f"{minutes}:{seconds:02d}"
            else:
                duration_str = "Unknown"

            item.setText(f"{title}\n{uploader} • {duration_str}")

            thumbnail_filename = metadata.get('thumbnail_filename')
            if thumbnail_filename:
                thumbnail_path = self.metadata_dir / thumbnail_filename
                if thumbnail_path.exists():
                    try:
                        pixmap = QPixmap(str(thumbnail_path))
                        if not pixmap.isNull():
                            pixmap = pixmap.scaled(60, 40, Qt.AspectRatioMode.KeepAspectRatio,
                                                   Qt.TransformationMode.SmoothTransformation)
                            item.setIcon(QIcon(pixmap))
                    except Exception as e:
                        print(f"Error loading thumbnail {thumbnail_path}: {e}")

            self.video_data[item] = video_path
            self.video_list.addItem(item)

    def on_video_double_clicked(self, item):
        if item in self.video_data:
            video_path = self.video_data[item]
            self.video_selected.emit(video_path)