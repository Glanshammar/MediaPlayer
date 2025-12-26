from PyQt6.QtCore import Qt, QEvent, QObject, QSettings, QTimer
from PyQt6.QtGui import QIcon, QAction, QKeyEvent, QActionGroup
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QStyle,
    QSlider,
    QFileDialog,
    QLabel,
    QStatusBar,
    QToolBar,
    QInputDialog,
    QMessageBox,
    QMenu
)
from pathlib import Path
from typing import cast
from downloadworker import DownloadWorker
from sidebar import VideoSidebar
import vlc
import sys
import gc

time_start : str = "00:00 / 00:00"

class MediaPlayer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        screen_geometry = self.screen().availableGeometry()
        width = int(screen_geometry.width() * 0.8)
        height = int(screen_geometry.height() * 0.8)
        self.resize(width, height)

        self.setWindowTitle("Media Player")
        self.setWindowIcon(QIcon("app_icon.png"))

        x = screen_geometry.x() + (screen_geometry.width() - width) // 2
        y = screen_geometry.y() + (screen_geometry.height() - height) // 2
        self.move(x, y)
        self.is_fullscreen = False
        self.current_position = 0
        self.is_playing = False
        self.sidebar_visible = True

        self.video_widget = QVideoWidget()

        self.setup_vlc_player()
        self.setup_ui()
        self.settings = QSettings("MediaPlayer", "MediaPlayer")
        self.load_settings()

        self.setup_connections()
        self.video_widget.installEventFilter(self)
        self.installEventFilter(self)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(100)  # Update every 100ms

    def setup_vlc_player(self):
        try:
            vlc_args = [
                '--no-xlib',  # Don't use Xlib (Linux)
                '--intf', 'dummy',
                '--no-video-title-show',
                '--no-snapshot-preview',
                '--quiet',
                '--file-caching=1000',
                '--network-caching=1000'
            ]

            self.vlc_instance = vlc.Instance(vlc_args)
            self.vlc_player = self.vlc_instance.media_player_new()
        except Exception as e:
            QMessageBox.critical(self, "VLC Error",
                                 f"Failed to initialize VLC player:\n{str(e)}\n\n"
                                 f"Make sure VLC is installed from: https://www.videolan.org/vlc/")
            raise

    def setup_ui(self) -> None:
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QHBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.create_sidebar()

        self.video_container = QWidget()
        self.video_container_layout = QVBoxLayout(self.video_container)
        self.video_container_layout.setContentsMargins(0, 0, 0, 0)
        self.video_container_layout.setSpacing(0)
        self.video_container_layout.addWidget(self.video_widget, 1)

        self.controls_widget = QWidget()
        self.controls_layout = QHBoxLayout(self.controls_widget)
        self.controls_layout.setContentsMargins(5, 5, 5, 5)

        self.play_button = QPushButton()
        style = self.style()
        if style:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Play")
        self.controls_layout.addWidget(self.play_button)

        self.stop_button = QPushButton()
        if style:
            self.stop_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setToolTip("Stop")
        self.controls_layout.addWidget(self.stop_button)

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderPressed.connect(self.position_slider_pressed)
        self.position_slider.sliderReleased.connect(self.position_slider_released)
        self.controls_layout.addWidget(self.position_slider)

        self.position_label = QLabel(time_start)
        self.controls_layout.addWidget(self.position_label)

        volume_layout = QHBoxLayout()
        self.volume_button = QPushButton()
        if style:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        volume_layout.addWidget(self.volume_button)

        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)  # Default volume
        volume_layout.addWidget(self.volume_slider)

        self.controls_layout.addLayout(volume_layout)
        self.video_container_layout.addWidget(self.controls_widget)

        self.main_layout.addWidget(self.sidebar)
        self.main_layout.addWidget(self.video_container, 1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.create_menu_bar()
        self.create_toolbar()

        download_dir = Path.home() / "MediaPlayer"
        metadata_dir = download_dir / "metadata"
        self.sidebar.set_metadata_dir(metadata_dir)
        self.sidebar.refresh_video_list()

    def create_sidebar(self):
        self.sidebar = VideoSidebar(self)
        self.sidebar.video_selected.connect(self.load_media_from_sidebar)

    def create_menu_bar(self) -> None:
        menu_bar = self.menuBar()
        if not menu_bar:
            return

        file_menu = menu_bar.addMenu("&File")
        if not file_menu:
            return

        open_action = QAction(QIcon.fromTheme("document-open"), "&Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        download_action_video = QAction("Download Video", self)
        download_action_video.setShortcut("Ctrl+U")
        download_action_video.triggered.connect(lambda checked, fmt="video": self.download_video(fmt))
        file_menu.addAction(download_action_video)

        download_action_audio = QAction("Download Audio", self)
        download_action_audio.setShortcut("Ctrl+alt+U")
        download_action_audio.triggered.connect(lambda checked, fmt="audio": self.download_video(fmt))
        file_menu.addAction(download_action_audio)

        file_menu.addSeparator()

        self.sidebar_action = QAction("&Toggle Video Library", self)
        self.sidebar_action.setShortcut("Ctrl+L")
        self.sidebar_action.triggered.connect(self.toggle_sidebar)
        file_menu.addAction(self.sidebar_action)

        exit_action = QAction(QIcon.fromTheme("application-exit"), "E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menu_bar.addMenu("&View")
        if not view_menu:
            return

        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        fullscreen_action.setCheckable(True)
        view_menu.addAction(fullscreen_action)
        self.fullscreen_action = fullscreen_action

        playback_menu = menu_bar.addMenu("&Playback")
        if not playback_menu:
            return

        skip_forward_action = QAction("Skip &Forward 5 Seconds", self)
        skip_forward_action.setShortcut("Right")
        skip_forward_action.triggered.connect(self.skip_forward)
        playback_menu.addAction(skip_forward_action)

        skip_backward_action = QAction("Skip &Backward 5 Seconds", self)
        skip_backward_action.setShortcut("Left")
        skip_backward_action.triggered.connect(self.skip_backward)
        playback_menu.addAction(skip_backward_action)

        increase_speed_action = QAction("Increase &Speed", self)
        increase_speed_action.setShortcut("Ctrl+Up")
        increase_speed_action.triggered.connect(self.increase_speed)
        playback_menu.addAction(increase_speed_action)

        decrease_speed_action = QAction("Decrease &Speed", self)
        decrease_speed_action.setShortcut("Ctrl+Down")
        decrease_speed_action.triggered.connect(self.decrease_speed)
        playback_menu.addAction(decrease_speed_action)

        reset_speed_action = QAction("&Reset Speed", self)
        reset_speed_action.setShortcut("Ctrl+R")
        reset_speed_action.triggered.connect(self.reset_speed)
        playback_menu.addAction(reset_speed_action)

        help_menu = menu_bar.addMenu("&Help")
        if not help_menu:
            return

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)

        subtitles_menu = menu_bar.addMenu("&Subtitles")
        if not subtitles_menu:
            return

        load_subtitle_action = QAction("&Load Subtitle File...", self)
        load_subtitle_action.setShortcut("Ctrl+S")
        load_subtitle_action.triggered.connect(self.load_subtitle_file)
        subtitles_menu.addAction(load_subtitle_action)

        remove_subtitle_action = QAction("&Remove Subtitle", self)
        remove_subtitle_action.setShortcut("Ctrl+Shift+S")
        remove_subtitle_action.triggered.connect(self.remove_subtitle)
        subtitles_menu.addAction(remove_subtitle_action)

        subtitles_menu.addSeparator()

        self.subtitle_track_menu = subtitles_menu.addMenu("&Track")
        self.no_subtitle_action = QAction("&No Subtitle", self)
        self.no_subtitle_action.setCheckable(True)
        self.no_subtitle_action.setChecked(True)
        self.no_subtitle_action.triggered.connect(lambda: self.set_subtitle_track(-1))
        self.subtitle_track_menu.addAction(self.no_subtitle_action)

        self.subtitle_track_group = QActionGroup(self)
        self.subtitle_track_group.setExclusive(True)
        self.no_subtitle_action.setActionGroup(self.subtitle_track_group)

    def create_toolbar(self) -> None:
        self.toolbar = QToolBar("Media Controls")
        self.addToolBar(self.toolbar)

        style = self.style()
        if not style:
            return

        open_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open", self)
        open_action.triggered.connect(self.open_file)
        self.toolbar.addAction(open_action)

        self.sidebar_toolbar_action = QAction(QIcon.fromTheme("view-list-details"), "Toggle Video Library", self)
        self.sidebar_toolbar_action.triggered.connect(self.toggle_sidebar)
        self.toolbar.addAction(self.sidebar_toolbar_action)

        download_action_video = QAction(QIcon("download_video.png"), "Download Video", self)
        download_action_video.triggered.connect(lambda checked, fmt="video": self.download_video(fmt))
        self.toolbar.addAction(download_action_video)

        download_action_audio = QAction(QIcon("download_audio.png"), "Download Audio", self)
        download_action_audio.triggered.connect(lambda checked, fmt="audio": self.download_video(fmt))
        self.toolbar.addAction(download_action_audio)

        fullscreen_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton), "Fullscreen", self)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.toolbar.addAction(fullscreen_action)

        skip_backward_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward), "Skip Backward",
                                       self)
        skip_backward_action.triggered.connect(self.skip_backward)
        self.toolbar.addAction(skip_backward_action)

        skip_forward_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward), "Skip Forward",
                                      self)
        skip_forward_action.triggered.connect(self.skip_forward)
        self.toolbar.addAction(skip_forward_action)

    def setup_connections(self) -> None:
        self.play_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.stop)
        self.volume_button.clicked.connect(self.toggle_mute)
        self.position_slider.sliderMoved.connect(self.set_position_from_slider)
        self.volume_slider.valueChanged.connect(self.set_volume)

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible

        if self.sidebar_visible:
            self.sidebar.show()
        else:
            self.sidebar.hide()

        self.save_settings()

    def load_media_from_sidebar(self, video_path):
        self.load_media(video_path)
        self.play()

    def position_slider_pressed(self):
        self.ui_timer.stop()

    def position_slider_released(self):
        self.ui_timer.start(100)

    def set_position_from_slider(self, position):
        if self.vlc_player.get_media():
            duration = self.vlc_player.get_length()
            if duration > 0:
                new_position = int((position / 100.0) * duration)
                self.set_position(new_position)

    def update_ui(self):
        if self.vlc_player.get_media():
            position = self.vlc_player.get_time()
            duration = self.vlc_player.get_length()

            if duration > 0:
                self.position_slider.blockSignals(True)
                slider_value = int((position / duration) * 100) if duration > 0 else 0
                self.position_slider.setValue(slider_value)
                self.position_slider.blockSignals(False)
                current_time = self.format_time(position)
                total_time = self.format_time(duration)
                self.position_label.setText(f"{current_time} / {total_time}")

            is_playing = self.vlc_player.is_playing()
            if is_playing != self.is_playing:
                self.is_playing = is_playing
                style = self.style()
                if style:
                    if is_playing:
                        self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
                        self.play_button.setToolTip("Pause")
                        self.status_bar.showMessage("Playing")
                    else:
                        self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
                        self.play_button.setToolTip("Play")
                        if position > 0 and position < duration:
                            self.status_bar.showMessage("Paused")

    def format_time(self, ms):
        if ms < 0:
            ms = 0
        seconds = ms // 1000
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def open_file(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Media File",
                str(Path.home()) + "/MediaPlayer",
                "Media Files (*.mp3 *.mp4 *.avi *.mkv *.wav *.flac *.ogg *.webm *.mov *.m4a *.3gp *.flv *.wmv *.mpeg *.mpg);;All Files (*)"
            )

            if file_path:
                self.load_media(file_path)
                self.status_bar.showMessage(f"Loaded: {Path(file_path).name}")
                self.play()
        except Exception as e:
            self.status_bar.showMessage(f"Error opening file: {str(e)}")

    def download_video(self, media_format="video") -> None:
        url, ok = QInputDialog.getText(
            self,
            f"Download {media_format}",
            f"Enter {media_format} URL (video or playlist):"
        )

        if ok and url:
            # Store current status bar message to restore later
            self.original_status_message = self.status_bar.currentMessage()

            # Show initial message
            self.status_bar.showMessage(f"Starting {media_format} download...")

            download_dir = Path.home() / "MediaPlayer"
            download_dir.mkdir(exist_ok=True)

            # Don't create permanent widgets - just update status bar
            # This avoids threading issues with UI widgets

            self.download_thread = DownloadWorker(url, str(download_dir), media_format)
            self.download_thread.finished.connect(self.on_download_finished)
            self.download_thread.progress.connect(self.on_download_progress)
            self.download_thread.metadata_saved.connect(self.on_metadata_saved)
            self.download_thread.start()

    def on_metadata_saved(self):
        if self.sidebar.isVisible():
            self.sidebar.refresh_video_list()

    def on_download_progress(self, progress_info: dict):
        try:
            progress_type = progress_info.get('type', '')

            if progress_type == 'playlist_info':
                total = progress_info.get('total', 0)
                title = progress_info.get('title', 'Playlist')
                self.status_bar.showMessage(f"Playlist: {title} ({total} videos)")

            elif progress_type == 'video_info':
                title = progress_info.get('title', 'Unknown')
                self.status_bar.showMessage(f"Downloading: {title}")

            elif progress_type == 'progress':
                title = progress_info.get('title', 'Unknown')
                current = progress_info.get('current', 1)
                total = progress_info.get('total', 1)
                percent = progress_info.get('percent', 0)
                speed = progress_info.get('speed', '')
                eta = progress_info.get('eta', '')

                if total > 1:
                    status_msg = f"({current}/{total}) {title} - {percent:.1f}%"
                else:
                    status_msg = f"{title} - {percent:.1f}%"

                if speed and speed != 'N/A':
                    status_msg += f" | {speed}"
                if eta and eta != 'N/A':
                    status_msg += f" | ETA: {eta}"

                self.status_bar.showMessage(status_msg)

            elif progress_type == 'finished_video':
                title = progress_info.get('title', 'Unknown')
                current = progress_info.get('current', 1)
                total = progress_info.get('total', 1)

                if total > 1:
                    self.status_bar.showMessage(f"Completed {current}/{total}: {title}")
                else:
                    self.status_bar.showMessage(f"Completed: {title}")
        except Exception as e:
            print(f"Error in progress handler: {e}")

    def on_download_finished(self, success: bool, message: str):
        try:
            if success:
                self.status_bar.showMessage(f"✓ {message}", 5000)
            else:
                self.status_bar.showMessage(f"✗ {message}", 5000)
                QMessageBox.warning(self, "Download Failed", message)

            QTimer.singleShot(5000, lambda: self.status_bar.showMessage(
                self.original_status_message if hasattr(self, 'original_status_message') else "Ready"))
        except Exception as e:
            print(f"Error in download finished handler: {e}")

    def load_media(self, file_path):
        try:
            self.current_media_path = file_path

            if sys.platform.startswith('win'):
                self.vlc_player.set_hwnd(int(self.video_widget.winId()))
            elif sys.platform.startswith('linux'):
                self.vlc_player.set_xwindow(int(self.video_widget.winId()))
            elif sys.platform.startswith('darwin'):
                self.vlc_player.set_nsobject(int(self.video_widget.winId()))

            media = self.vlc_instance.media_new(file_path)
            self.vlc_player.set_media(media)

            self.current_subtitle_track = -1
            self.external_subtitle_path = None
            self.subtitle_delay = 0

            self.clear_subtitle_track_actions()

            self.no_subtitle_action = QAction("No Subtitle", self)
            self.no_subtitle_action.setCheckable(True)
            self.no_subtitle_action.setChecked(True)
            self.no_subtitle_action.triggered.connect(lambda: self.set_subtitle_track(-1))
            self.no_subtitle_action.setActionGroup(self.subtitle_track_group)
            self.subtitle_track_menu.addAction(self.no_subtitle_action)

            self.position_slider.setValue(0)
            self.position_label.setText("Loaded media successfully")
            self.status_bar.showMessage(f"Loaded: {Path(file_path).name}")
            QTimer.singleShot(500, self.detect_embedded_subtitles)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load media:\n{str(e)}")

    def toggle_playback(self):
        if self.vlc_player.get_media():
            if self.vlc_player.is_playing():
                self.pause()
            else:
                self.play()

    def play(self):
        if self.vlc_player.get_media():
            self.vlc_player.play()
            self.is_playing = True

    def pause(self):
        if self.vlc_player.get_media():
            self.vlc_player.pause()
            self.is_playing = False

    def stop(self):
        if self.vlc_player.get_media():
            self.vlc_player.stop()
            self.position_slider.setValue(0)
            self.position_label.setText(time_start)
            self.is_playing = False

        style = self.style()
        if style:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Play")
        self.status_bar.showMessage("Stopped")

    def toggle_fullscreen(self) -> None:
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self) -> None:
        self.ui_states_before_fullscreen = {
            'controls_visible': all(w.isVisible() for w in [self.play_button, self.stop_button, self.position_slider]),
            'volume_layout_visible': self.volume_button.isVisible() and self.volume_slider.isVisible(),
            'toolbar_visible': self.toolbar.isVisible() if hasattr(self, 'toolbar') else False,
            'statusbar_visible': self.statusBar().isVisible() if self.statusBar() else False,
            'menubar_visible': self.menuBar().isVisible() if self.menuBar() else False
        }

        if hasattr(self, 'toolbar'):
            self.toolbar.hide()

        for i in range(self.controls_layout.count()):
            item = self.controls_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.hide()

        if self.volume_button:
            self.volume_button.hide()
        if self.volume_slider:
            self.volume_slider.hide()

        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.hide()

        menu_bar = self.menuBar()
        if menu_bar is not None:
            menu_bar.hide()

        self.showFullScreen()
        self.is_fullscreen = True
        if hasattr(self, 'fullscreen_action'):
            self.fullscreen_action.setChecked(True)

    def exit_fullscreen(self) -> None:
        self.showNormal()
        self.is_fullscreen = False

        for i in range(self.controls_layout.count()):
            item = self.controls_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None and self.ui_states_before_fullscreen.get('controls_visible', True):
                    widget.show()

        if self.ui_states_before_fullscreen.get('volume_layout_visible', True):
            if self.volume_button:
                self.volume_button.show()
            if self.volume_slider:
                self.volume_slider.show()

        if hasattr(self, 'toolbar') and self.ui_states_before_fullscreen.get('toolbar_visible', True):
            self.toolbar.show()

        status_bar = self.statusBar()
        if status_bar is not None and self.ui_states_before_fullscreen.get('statusbar_visible', True):
            status_bar.show()

        menu_bar = self.menuBar()
        if menu_bar is not None and self.ui_states_before_fullscreen.get('menubar_visible', True):
            menu_bar.show()

        if hasattr(self, 'fullscreen_action'):
            self.fullscreen_action.setChecked(False)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            if key_event.key() == Qt.Key.Key_Right:
                self.skip_forward()
                self.status_bar.showMessage("Skipped forward 5 seconds", 2000)
                return True
            elif key_event.key() == Qt.Key.Key_Left:
                self.skip_backward()
                self.status_bar.showMessage("Skipped backward 5 seconds", 2000)
                return True
            elif key_event.key() == Qt.Key.Key_Up:
                self.increase_volume()
                return True
            elif key_event.key() == Qt.Key.Key_Down:
                self.decrease_volume()
                return True
        elif event.type() == QEvent.Type.MouseButtonDblClick and obj is self.video_widget:
            self.toggle_fullscreen()
            return True

        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        modifiers = event.modifiers()

        if key == Qt.Key.Key_F:
            self.toggle_fullscreen()
        elif key == Qt.Key.Key_Escape and self.is_fullscreen:
            self.exit_fullscreen()
        elif key == Qt.Key.Key_Right:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.next_media()
                self.status_bar.showMessage("Went to next media.", 2000)
            else:
                self.skip_forward()
                self.status_bar.showMessage("Skipped forward 5 seconds.", 2000)
        elif key == Qt.Key.Key_Left:
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                self.previous_media()
                self.status_bar.showMessage("Went to previous media.", 2000)
            else:
                self.skip_backward()
                self.status_bar.showMessage("Skipped backward 5 seconds.", 2000)
        elif key == Qt.Key.Key_Up:
            self.increase_volume()
        elif key == Qt.Key.Key_Down:
            self.decrease_volume()
        elif key == Qt.Key.Key_Space:
            self.toggle_playback()
        elif key == Qt.Key.Key_M:
            self.toggle_mute()
        elif key == Qt.Key.Key_0:  # Reset to beginning
            self.set_position(0)
        elif key == Qt.Key.Key_Home:  # Beginning
            self.set_position(0)
        elif key == Qt.Key.Key_End:  # End
            if hasattr(self, 'vlc_player') and self.vlc_player.get_media():
                self.set_position(self.vlc_player.get_length())
        elif key == Qt.Key.Key_Up and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.increase_speed()
        elif key == Qt.Key.Key_Down and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.decrease_speed()
        elif key == Qt.Key.Key_R and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.reset_speed()
        elif key == Qt.Key.Key_N and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.next_media()
        elif key == Qt.Key.Key_P and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.previous_media()
        else:
            super().keyPressEvent(event)

    def skip_forward(self) -> None:
        if self.vlc_player.get_media():
            current_position = self.vlc_player.get_time()
            duration = self.vlc_player.get_length()
            if duration > 0:
                new_position = min(current_position + 5000, duration)
                self.set_position(new_position)

    def skip_backward(self) -> None:
        if self.vlc_player.get_media():
            current_position = self.vlc_player.get_time()
            new_position = max(0, current_position - 5000)
            self.set_position(new_position)

    def set_position(self, position_ms):
        if self.vlc_player.get_media():
            self.vlc_player.set_time(int(position_ms))

    def set_volume(self, volume):
        self.vlc_player.audio_set_volume(volume)
        style = self.style()
        if not style:
            return

        if volume <= 0:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
        else:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))

    def toggle_mute(self):
        self.vlc_player.audio_toggle_mute()
        style = self.style()
        if not style:
            return

        volume = self.vlc_player.audio_get_volume()
        if volume <= 0:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
        else:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
            self.volume_slider.setValue(volume)

    def about(self) -> None:
        self.status_bar.showMessage("Media Player - A PyQt6 based media player application")

    def increase_volume(self) -> None:
        current_volume = self.vlc_player.audio_get_volume()
        new_volume = min(100, current_volume + 5)
        self.vlc_player.audio_set_volume(new_volume)
        self.volume_slider.setValue(new_volume)
        self.status_bar.showMessage(f"Volume: {new_volume}%", 2000)

    def decrease_volume(self) -> None:
        current_volume = self.vlc_player.audio_get_volume()
        new_volume = max(0, current_volume - 5)
        self.vlc_player.audio_set_volume(new_volume)
        self.volume_slider.setValue(new_volume)
        self.status_bar.showMessage(f"Volume: {new_volume}%", 2000)

    def load_settings(self) -> None:
        self.restoreGeometry(self.settings.value("windowGeometry", b""))
        volume = self.settings.value("volume", 100, type=int)
        self.volume_slider.setValue(volume)
        self.set_volume(volume)
        self.recent_files = self.settings.value("recentFiles", [], type=list)

        sidebar_visible = self.settings.value("sidebar_visible", True, type=bool)
        self.sidebar_visible = sidebar_visible
        if not self.sidebar_visible:
            self.sidebar.hide()

    def save_settings(self) -> None:
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("volume", self.volume_slider.value())
        self.settings.setValue("recentFiles", self.recent_files[-10:])  # Keep last 10
        self.settings.setValue("sidebar_visible", self.sidebar_visible)

    def increase_speed(self):
        if self.vlc_player.get_media():
            current_rate = self.vlc_player.get_rate()
            new_rate = min(4.0, current_rate + 0.05)
            self.vlc_player.set_rate(new_rate)
            self.status_bar.showMessage(f"Speed: {new_rate:.2f}x", 2000)

    def decrease_speed(self):
        if self.vlc_player.get_media():
            current_rate = self.vlc_player.get_rate()
            new_rate = max(0.25, current_rate - 0.05)
            self.vlc_player.set_rate(new_rate)
            self.status_bar.showMessage(f"Speed: {new_rate:.2f}x", 2000)

    def reset_speed(self):
        if self.vlc_player.get_media():
            self.vlc_player.set_rate(1.0)
            self.status_bar.showMessage("Speed: 1.00x", 2000)

    def detect_embedded_subtitles(self):
        try:
            if not self.vlc_player.get_media():
                return

            track_descriptions = self.vlc_player.video_get_spu_description()

            if track_descriptions:
                self.subtitle_tracks = []
                for track in track_descriptions:
                    track_id = track[0]
                    track_name_bytes = track[1]

                    if track_name_bytes is None:
                        track_name = f"Subtitle Track {len(self.subtitle_tracks) + 1}"
                    elif isinstance(track_name_bytes, bytes):
                        try:
                            # Try UTF-8 first (most common)
                            track_name = track_name_bytes.decode('utf-8', errors='ignore')
                        except UnicodeDecodeError:
                            # If UTF-8 fails, try Latin-1 (which will never fail)
                            track_name = track_name_bytes.decode('latin-1', errors='ignore')

                        track_name = track_name.strip()
                        if not track_name:
                            track_name = f"Subtitle Track {len(self.subtitle_tracks) + 1}"
                    else:
                        # If it's already a string (shouldn't happen but just in case)
                        track_name = str(track_name_bytes)

                    self.subtitle_tracks.append((track_id, track_name))

                    track_action = QAction(track_name, self)
                    track_action.setCheckable(True)
                    track_action.triggered.connect(lambda checked, tid=track_id: self.set_subtitle_track(tid))
                    track_action.setActionGroup(self.subtitle_track_group)
                    self.subtitle_track_menu.addAction(track_action)

                self.status_bar.showMessage(f"Found {len(track_descriptions)} embedded subtitle track(s)", 3000)
            else:
                self.subtitle_tracks = []
                self.status_bar.showMessage("No embedded subtitles found", 2000)
        except Exception as e:
            print(f"Error detecting subtitles: {e}")

    def load_subtitle_file(self):
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Subtitle File",
                str(Path.home()),
                "Subtitle Files (*.srt *.sub *.ass *.ssa *.vtt *.txt);;All Files (*)"
            )

            if file_path:
                if self.external_subtitle_path:
                    self.vlc_player.video_set_subtitle_file(None)

                if self.vlc_player.video_set_subtitle_file(file_path):
                    self.external_subtitle_path = file_path
                    self.current_subtitle_track = 0  # External subtitles are track 0
                    self.clear_subtitle_track_actions()

                    subtitle_name = Path(file_path).name
                    external_action = QAction(f"External: {subtitle_name}", self)
                    external_action.setCheckable(True)
                    external_action.setChecked(True)
                    external_action.triggered.connect(lambda: self.enable_external_subtitle())
                    external_action.setActionGroup(self.subtitle_track_group)
                    self.subtitle_track_menu.addAction(external_action)

                    self.no_subtitle_action = QAction("No Subtitle", self)
                    self.no_subtitle_action.setCheckable(True)
                    self.no_subtitle_action.triggered.connect(lambda: self.set_subtitle_track(-1))
                    self.no_subtitle_action.setActionGroup(self.subtitle_track_group)
                    self.subtitle_track_menu.addAction(self.no_subtitle_action)

                    self.status_bar.showMessage(f"Loaded subtitle: {subtitle_name}")
                else:
                    QMessageBox.warning(self, "Subtitle Error",
                                        "Failed to load subtitle file. The file might be corrupted or in an unsupported format.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load subtitle file:\n{str(e)}")

    def enable_external_subtitle(self):
        if self.external_subtitle_path:
            self.vlc_player.video_set_subtitle_file(self.external_subtitle_path)
            self.current_subtitle_track = 0
            self.status_bar.showMessage("External subtitle enabled", 2000)

    def set_subtitle_track(self, track_id: int):
        try:
            if track_id == -1:
                if self.current_subtitle_track == 0:  # External subtitle
                    self.vlc_player.video_set_subtitle_file(None)
                else:  # Embedded subtitle
                    self.vlc_player.video_set_spu(-1)  # Disable all subtitles

                self.current_subtitle_track = -1
                self.status_bar.showMessage("Subtitles disabled", 2000)
            elif track_id == 0:  # External subtitle
                if self.external_subtitle_path:
                    self.vlc_player.video_set_subtitle_file(self.external_subtitle_path)
                    self.vlc_player.video_set_spu(-1)  # Disable embedded
                    self.current_subtitle_track = 0
                    self.status_bar.showMessage("External subtitle enabled", 2000)
            else:  # Embedded subtitle
                if self.external_subtitle_path:
                    self.vlc_player.video_set_subtitle_file(None)

                if self.vlc_player.video_set_spu(track_id):
                    self.current_subtitle_track = track_id
                    track_name = next((name for tid, name in self.subtitle_tracks if tid == track_id),
                                      f"Track {track_id}")
                    self.status_bar.showMessage(f"Subtitle: {track_name}", 2000)
                else:
                    self.status_bar.showMessage(f"Failed to enable subtitle track {track_id}", 2000)
        except Exception as e:
            print(f"Error setting subtitle track: {e}")

    def remove_subtitle(self):
        if self.current_subtitle_track != -1:
            self.set_subtitle_track(-1)

            if hasattr(self, 'no_subtitle_action'):
                self.no_subtitle_action.setChecked(True)

            self.status_bar.showMessage("Subtitle removed", 2000)

    def show_subtitle_menu(self):
        if hasattr(self, 'subtitle_track_menu'):
            popup_menu = QMenu(self)

            load_action = popup_menu.addAction("Load Subtitle File...")
            load_action.triggered.connect(self.load_subtitle_file)

            if self.current_subtitle_track != -1:
                remove_action = popup_menu.addAction("Remove Subtitle")
                remove_action.triggered.connect(self.remove_subtitle)

            popup_menu.addSeparator()
            tracks_menu = popup_menu.addMenu("Tracks")

            no_sub_action = tracks_menu.addAction("No Subtitle")
            no_sub_action.setCheckable(True)
            no_sub_action.setChecked(self.current_subtitle_track == -1)
            no_sub_action.triggered.connect(lambda: self.set_subtitle_track(-1))

            tracks_menu.addSeparator()

            if self.external_subtitle_path:
                ext_action = tracks_menu.addAction(f"External: {Path(self.external_subtitle_path).name}")
                ext_action.setCheckable(True)
                ext_action.setChecked(self.current_subtitle_track == 0)
                ext_action.triggered.connect(self.enable_external_subtitle)

            for track_id, track_name in self.subtitle_tracks:
                track_action = tracks_menu.addAction(track_name)
                track_action.setCheckable(True)
                track_action.setChecked(self.current_subtitle_track == track_id)
                track_action.triggered.connect(lambda checked, tid=track_id: self.set_subtitle_track(tid))

            popup_menu.exec(self.cursor().pos())

    def clear_subtitle_track_actions(self):
        actions = self.subtitle_track_menu.actions()
        for action in actions:
            self.subtitle_track_menu.removeAction(action)

        for action in self.subtitle_track_group.actions():
            self.subtitle_track_group.removeAction(action)

    def closeEvent(self, event):
        try:
            if hasattr(self, 'ui_timer'):
                self.ui_timer.stop()

            if self.is_fullscreen:
                self.exit_fullscreen()

            if hasattr(self, 'download_thread') and self.download_thread.isRunning():
                self.download_thread.stop()
                self.download_thread.wait(2000)  # 2 seconds timeout
                if self.download_thread.isRunning():
                    self.download_thread.terminate()
                    self.download_thread.wait()

            if hasattr(self, 'vlc_player'):
                try:
                    self.vlc_player.stop()
                    media = self.vlc_player.get_media()
                    if media:
                        media.release()
                    self.vlc_player.release()
                except Exception as e:
                    print(f"Error releasing VLC player: {e}")

            if hasattr(self, 'vlc_instance'):
                try:
                    self.vlc_instance.release()
                except Exception as e:
                    print(f"Error releasing VLC instance: {e}")

            if hasattr(self, 'external_subtitle_path'):
                try:
                    if hasattr(self, 'vlc_player'):
                        self.vlc_player.video_set_subtitle_file(None)
                except Exception as e:
                    print(f"Error releasing subtitles: {e}")

            if hasattr(self, 'download_status_label'):
                try:
                    self.status_bar.removeWidget(self.download_status_label)
                except Exception as e:
                    print(f"Error removing download status label: {e}")

            if hasattr(self, 'download_progress_bar'):
                try:
                    self.status_bar.removeWidget(self.download_progress_bar)
                except Exception as e:
                    print(f"Error removing download progress bar: {e}")

            self.save_settings()
            gc.collect()
        except Exception as e:
            print(f"Error during close event: {e}")
        finally:
            super().closeEvent(event)