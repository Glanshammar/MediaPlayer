from PyQt6.QtCore import Qt, QEvent, QObject, QSettings, QTimer
from PyQt6.QtGui import QIcon, QAction, QKeyEvent
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
    QMessageBox
)
from pathlib import Path
from typing import cast
from downloadworker import DownloadWorker
import vlc
import sys

time_start : str = "00:00 / 00:00"

class MediaPlayer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        screen_geometry = self.screen().availableGeometry()
        width = int(screen_geometry.width() * 0.8)
        height = int(screen_geometry.height() * 0.8)
        self.resize(width, height)

        self.setWindowTitle("Media Player")

        x = screen_geometry.x() + (screen_geometry.width() - width) // 2
        y = screen_geometry.y() + (screen_geometry.height() - height) // 2
        self.move(x, y)
        self.is_fullscreen = False
        self.current_position = 0
        self.is_playing = False

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

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.addWidget(self.video_widget)

        self.controls_layout = QHBoxLayout()

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
        self.main_layout.addLayout(self.controls_layout)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        self.create_menu_bar()
        self.create_toolbar()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

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

        download_action = QAction("Download Video", self)
        download_action.setShortcut("Ctrl+U")
        download_action.triggered.connect(self.download_video)
        file_menu.addAction(download_action)

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

    def create_toolbar(self) -> None:
        self.toolbar = QToolBar("Media Controls")
        self.addToolBar(self.toolbar)

        style = self.style()
        if not style:
            return

        open_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open", self)
        open_action.triggered.connect(self.open_file)
        self.toolbar.addAction(open_action)

        download_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_ToolBarVerticalExtensionButton), "Download Video", self)
        download_action.triggered.connect(self.download_video)
        self.toolbar.addAction(download_action)

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

    def download_video(self) -> None:
        url, ok = QInputDialog.getText(
            self,
            "Download video",
            "Enter video/playlist URL:"
        )

        if ok and url:
            self.status_bar.showMessage("Downloading video...")
            download_dir = Path.home() / "MediaPlayer"
            download_dir.mkdir(exist_ok=True)

            self.download_thread = DownloadWorker(url, str(download_dir))
            self.download_thread.finished.connect(self.on_download_finished)
            self.download_thread.start()

    def on_download_finished(self, success: bool, message: str):
        if success:
            self.status_bar.showMessage(message)
        else:
            self.status_bar.showMessage(message)
            QMessageBox.warning(self, "Download Failed", message)

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
            self.position_slider.setValue(0)
            self.position_label.setText("Loaded media successfully")
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

    def save_settings(self) -> None:
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("volume", self.volume_slider.value())
        self.settings.setValue("recentFiles", self.recent_files[-10:])  # Keep last 10

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

    def closeEvent(self, event):
        if self.is_fullscreen:
            self.exit_fullscreen()
        if hasattr(self, 'vlc_player'):
            self.vlc_player.stop()
            self.vlc_player.release()
        if hasattr(self, 'vlc_instance'):
            self.vlc_instance.release()
        self.save_settings()
        super().closeEvent(event)