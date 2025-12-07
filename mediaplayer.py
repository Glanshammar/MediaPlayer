from PyQt6.QtCore import Qt, QEvent, QObject, QSettings, QTimer
from PyQt6.QtGui import QIcon, QAction, QKeyEvent
from PyQt6.QtMultimedia import QAudioOutput
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
from typing import List, cast
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

        x = screen_geometry.x() + (screen_geometry.width() - width) // 2
        y = screen_geometry.y() + (screen_geometry.height() - height) // 2
        self.move(x, y)
        self.is_fullscreen = False
        self.current_position = 0
        self.is_playing = False

        self.video_widget = QVideoWidget()
        self.audio_output = QAudioOutput()

        self.setup_vlc_player()
        self.setup_ui()
        self.settings = QSettings("MediaPlayer", "MediaPlayer")
        self.load_settings()

        self.setup_connections()
        self.video_widget.installEventFilter(self)
        self.installEventFilter(self)

        self.playlist: List[Path] = []
        self.current_playlist_index = -1
        self.create_playlist_menu()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()

        # Setup UI update timer
        self.ui_timer = QTimer()
        self.ui_timer.timeout.connect(self.update_ui)
        self.ui_timer.start(100)  # Update every 100ms

    def setup_vlc_player(self):
        """Setup VLC player instance"""
        try:
            # Create VLC instance with options
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

        # File menu
        file_menu = menu_bar.addMenu("&File")
        if not file_menu:
            return

        # Open action
        open_action = QAction(QIcon.fromTheme("document-open"), "&Open", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        # Open URL action
        open_url_action = QAction("Open &URL", self)
        open_url_action.setShortcut("Ctrl+U")
        open_url_action.triggered.connect(self.open_url)
        file_menu.addAction(open_url_action)

        # Exit action
        exit_action = QAction(QIcon.fromTheme("application-exit"), "E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menu_bar.addMenu("&View")
        if not view_menu:
            return

        # Fullscreen action
        fullscreen_action = QAction("&Fullscreen", self)
        fullscreen_action.setShortcut("F")
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        fullscreen_action.setCheckable(True)
        view_menu.addAction(fullscreen_action)
        self.fullscreen_action = fullscreen_action

        # Playback menu
        playback_menu = menu_bar.addMenu("&Playback")
        if not playback_menu:
            return

        # Skip forward action
        skip_forward_action = QAction("Skip &Forward 5 Seconds", self)
        skip_forward_action.setShortcut("Right")
        skip_forward_action.triggered.connect(self.skip_forward)
        playback_menu.addAction(skip_forward_action)

        # Skip backward action
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

        # Help menu
        help_menu = menu_bar.addMenu("&Help")
        if not help_menu:
            return

        # About action
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.about)
        help_menu.addAction(about_action)

    def create_toolbar(self) -> None:
        """Create the application toolbar."""
        self.toolbar = QToolBar("Media Controls")
        self.addToolBar(self.toolbar)

        style = self.style()
        if not style:
            return

        # Open file action
        open_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "Open", self)
        open_action.triggered.connect(self.open_file)
        self.toolbar.addAction(open_action)

        # Open URL action
        open_url_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_FileLinkIcon), "Open URL", self)
        open_url_action.triggered.connect(self.open_url)
        self.toolbar.addAction(open_url_action)

        # Add fullscreen button to toolbar
        fullscreen_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton), "Fullscreen", self)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.toolbar.addAction(fullscreen_action)

        # Add skip backward button
        skip_backward_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward), "Skip Backward",
                                       self)
        skip_backward_action.triggered.connect(self.skip_backward)
        self.toolbar.addAction(skip_backward_action)

        # Add skip forward button
        skip_forward_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward), "Skip Forward",
                                      self)
        skip_forward_action.triggered.connect(self.skip_forward)
        self.toolbar.addAction(skip_forward_action)

    def setup_connections(self) -> None:
        """Set up signal and slot connections."""
        # Button connections
        self.play_button.clicked.connect(self.toggle_playback)
        self.stop_button.clicked.connect(self.stop)
        self.volume_button.clicked.connect(self.toggle_mute)

        # Slider connections
        self.position_slider.sliderMoved.connect(self.set_position_from_slider)
        self.volume_slider.valueChanged.connect(self.set_volume)

    def position_slider_pressed(self):
        """When user starts dragging the slider"""
        self.ui_timer.stop()

    def position_slider_released(self):
        """When user releases the slider"""
        self.ui_timer.start(100)

    def set_position_from_slider(self, position):
        """Set position from slider value (0-100)"""
        if self.vlc_player.get_media():
            duration = self.vlc_player.get_length()
            if duration > 0:
                new_position = int((position / 100.0) * duration)
                self.set_position(new_position)

    def update_ui(self):
        """Update UI elements (position, time, playback state)"""
        if self.vlc_player.get_media():
            # Update position
            position = self.vlc_player.get_time()
            duration = self.vlc_player.get_length()

            if duration > 0:
                # Update slider without triggering events
                self.position_slider.blockSignals(True)
                slider_value = int((position / duration) * 100) if duration > 0 else 0
                self.position_slider.setValue(slider_value)
                self.position_slider.blockSignals(False)

                # Update time label
                current_time = self.format_time(position)
                total_time = self.format_time(duration)
                self.position_label.setText(f"{current_time} / {total_time}")

            # Update play/pause button
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
        """Format milliseconds to HH:MM:SS or MM:SS"""
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
                str(Path.home()),
                "Media Files (*.mp3 *.mp4 *.avi *.mkv *.wav *.flac *.ogg *.webm *.mov *.m4a *.3gp *.flv *.wmv *.mpeg *.mpg);;All Files (*)"
            )

            if file_path:
                self.load_media(file_path)
                self.status_bar.showMessage(f"Loaded: {Path(file_path).name}")
                self.play()

        except Exception as e:
            self.status_bar.showMessage(f"Error opening file: {str(e)}")

    def open_url(self) -> None:
        url, ok = QInputDialog.getText(
            self,
            "Open URL",
            "Enter video URL:"
        )

        if ok and url:
            self.status_bar.showMessage("Downloading video...")

            # Create downloads directory if it doesn't exist
            download_dir = Path.home() / "MediaPlayer"
            download_dir.mkdir(exist_ok=True)

            # Start download in QThread
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
        """Load media file into VLC"""
        try:
            # Set the window handle for video output
            if sys.platform.startswith('win'):
                self.vlc_player.set_hwnd(int(self.video_widget.winId()))
            elif sys.platform.startswith('linux'):
                self.vlc_player.set_xwindow(int(self.video_widget.winId()))
            elif sys.platform.startswith('darwin'):
                self.vlc_player.set_nsobject(int(self.video_widget.winId()))

            # Create media and load it
            media = self.vlc_instance.media_new(file_path)
            self.vlc_player.set_media(media)

            # Reset UI
            self.position_slider.setValue(0)
            self.position_label.setText(time_start)

        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load media:\n{str(e)}")

    def toggle_playback(self):
        """Toggle between play and pause"""
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
        """Toggle fullscreen mode."""
        if self.is_fullscreen:
            self.exit_fullscreen()
        else:
            self.enter_fullscreen()

    def enter_fullscreen(self) -> None:
        """Enter true fullscreen mode."""
        # Save current visibility states
        self.ui_states_before_fullscreen = {
            'controls_visible': all(w.isVisible() for w in [self.play_button, self.stop_button, self.position_slider]),
            'toolbar_visible': self.toolbar.isVisible() if hasattr(self, 'toolbar') else False
        }

        # Hide all UI elements
        if hasattr(self, 'toolbar'):
            self.toolbar.hide()

        # Hide controls
        for i in range(self.controls_layout.count()):
            item = self.controls_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.hide()

        # Hide status bar and menu bar
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.hide()

        menu_bar = self.menuBar()
        if menu_bar is not None:
            menu_bar.hide()

        # Add video widget directly to the main layout as only child
        self.video_widget.setParent(None)
        for i in range(self.main_layout.count()):
            self.main_layout.removeItem(self.main_layout.itemAt(0))

        self.main_layout.addWidget(self.video_widget)
        self.video_widget.setFocus()

        # Switch to fullscreen state
        self.showFullScreen()
        self.is_fullscreen = True
        if hasattr(self, 'fullscreen_action'):
            self.fullscreen_action.setChecked(True)

    def exit_fullscreen(self) -> None:
        """Exit true fullscreen mode."""
        # Return to normal window state first
        self.showNormal()

        # Rebuild layout structure
        self.video_widget.setParent(None)
        for i in range(self.main_layout.count()):
            self.main_layout.removeItem(self.main_layout.itemAt(0))

        # Re-add video widget
        self.main_layout.addWidget(self.video_widget)

        # Re-add controls layout
        self.main_layout.addLayout(self.controls_layout)

        # Show all controls
        for i in range(self.controls_layout.count()):
            item = self.controls_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None and self.ui_states_before_fullscreen.get('controls_visible', True):
                    widget.show()

        # Show toolbar if it was visible before
        if hasattr(self, 'toolbar') and self.ui_states_before_fullscreen.get('toolbar_visible', True):
            self.toolbar.show()

        # Show status bar and menu bar
        status_bar = self.statusBar()
        if status_bar is not None:
            status_bar.show()

        menu_bar = self.menuBar()
        if menu_bar is not None:
            menu_bar.show()

        self.is_fullscreen = False
        if hasattr(self, 'fullscreen_action'):
            self.fullscreen_action.setChecked(False)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """Filter events for all child objects."""
        if event.type() == QEvent.Type.KeyPress:
            key_event = cast(QKeyEvent, event)
            # Handle arrow key presses
            if key_event.key() == Qt.Key.Key_Right:
                self.skip_forward()
                self.status_bar.showMessage("Skipped forward 10 seconds", 2000)
                return True
            elif key_event.key() == Qt.Key.Key_Left:
                self.skip_backward()
                self.status_bar.showMessage("Skipped backward 10 seconds", 2000)
                return True
            elif key_event.key() == Qt.Key.Key_Up:
                self.increase_volume()
                return True
            elif key_event.key() == Qt.Key.Key_Down:
                self.decrease_volume()
                return True
        # Handle double clicks on video widget
        elif event.type() == QEvent.Type.MouseButtonDblClick and obj is self.video_widget:
            self.toggle_fullscreen()
            return True

        # Let parent class handle the rest
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
            if self.vlc_player.get_media():
                self.set_position(self.vlc_player.get_length())
        elif key == Qt.Key.Key_Up and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.increase_speed()
        elif key == Qt.Key.Key_Down and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.decrease_speed()
        elif key == Qt.Key.Key_R and modifiers & Qt.KeyboardModifier.ControlModifier:
            self.reset_speed()
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
        """Set playback position in milliseconds"""
        if self.vlc_player.get_media():
            self.vlc_player.set_time(int(position_ms))

    def set_volume(self, volume):
        """Set volume (0-100)"""
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

        # Get current mute state (VLC doesn't have a direct method, so we check volume)
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

    def create_playlist_menu(self) -> None:
        menu_bar = self.menuBar()
        if not menu_bar:
            return

        playlist_menu = menu_bar.addMenu("&Playlist")

        # Add to playlist action
        add_to_playlist_action = QAction("&Add to Playlist", self)
        add_to_playlist_action.triggered.connect(self.add_to_playlist)
        playlist_menu.addAction(add_to_playlist_action)

        # Next/Previous actions
        next_action = QAction("&Next", self)
        next_action.setShortcut("Ctrl+Right")
        next_action.triggered.connect(self.next_media)
        playlist_menu.addAction(next_action)

        previous_action = QAction("&Previous", self)
        previous_action.setShortcut("Ctrl+Left")
        previous_action.triggered.connect(self.previous_media)
        playlist_menu.addAction(previous_action)

    def add_to_playlist(self) -> None:
        # For VLC, we need to track the current media differently
        # This is simplified - you may need to store the current file path
        pass

    def next_media(self) -> None:
        if self.playlist and self.current_playlist_index < len(self.playlist) - 1:
            self.current_playlist_index += 1
            self.load_playlist_item()

    def previous_media(self) -> None:
        if self.playlist and self.current_playlist_index > 0:
            self.current_playlist_index -= 1
            self.load_playlist_item()

    def load_playlist_item(self) -> None:
        if 0 <= self.current_playlist_index < len(self.playlist):
            file_path = self.playlist[self.current_playlist_index]
            self.load_media(str(file_path))
            self.status_bar.showMessage(
                f"Playing: {file_path.name} ({self.current_playlist_index + 1}/{len(self.playlist)})")
            self.play()

    def load_settings(self) -> None:
        # Window geometry
        self.restoreGeometry(self.settings.value("windowGeometry", b""))

        # Volume
        volume = self.settings.value("volume", 100, type=int)
        self.volume_slider.setValue(volume)
        self.set_volume(volume)

        # Recent files
        self.recent_files = self.settings.value("recentFiles", [], type=list)

    def save_settings(self) -> None:
        self.settings.setValue("windowGeometry", self.saveGeometry())
        self.settings.setValue("volume", self.volume_slider.value())
        self.settings.setValue("recentFiles", self.recent_files[-10:])  # Keep last 10

    def increase_speed(self):
        """Increase playback speed"""
        if self.vlc_player.get_media():
            current_rate = self.vlc_player.get_rate()
            new_rate = min(4.0, current_rate + 0.25)
            self.vlc_player.set_rate(new_rate)
            self.status_bar.showMessage(f"Speed: {new_rate:.2f}x", 2000)

    def decrease_speed(self):
        """Decrease playback speed"""
        if self.vlc_player.get_media():
            current_rate = self.vlc_player.get_rate()
            new_rate = max(0.25, current_rate - 0.25)
            self.vlc_player.set_rate(new_rate)
            self.status_bar.showMessage(f"Speed: {new_rate:.2f}x", 2000)

    def reset_speed(self):
        """Reset playback speed to normal"""
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