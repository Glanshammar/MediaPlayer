from PyQt6.QtCore import QUrl, Qt, QTime, QEvent, QObject, QSettings, QTimer
from PyQt6.QtGui import QIcon, QAction, QKeyEvent, QCloseEvent
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
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
    QInputDialog
)
from pathlib import Path
from typing import List, cast
from downloadworker import DownloadWorker


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
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)

        # Set the audio buffer size for better sync
        # self.audio_output.setBufferSize(2048)  # Larger buffer for smoother playback

        self.media_player.errorOccurred.connect(self.handle_error)
        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.media_player.setVideoOutput(self.video_widget)
        self.setup_ui()
        self.setup_connections()
        self.video_widget.installEventFilter(self) # Install event filter on video widget to handle double clicks
        self.installEventFilter(self) # Install event filter to capture all key events
        self.playlist: List[Path] = []
        self.current_playlist_index = -1
        self.create_playlist_menu()
        self.settings = QSettings("MediaPlayer", "MediaPlayer")
        self.load_settings()
        self.pending_download_path = None
        self.pending_download_url = None

    def setup_ui(self) -> None:
        """Set up the user interface."""
        # Create central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Main layout
        self.main_layout = QVBoxLayout(self.central_widget)

        # Add video widget
        self.main_layout.addWidget(self.video_widget)

        # Create controls layout
        self.controls_layout = QHBoxLayout()

        # Play/Pause button
        self.play_button = QPushButton()
        style = self.style()
        if style:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Play")
        self.controls_layout.addWidget(self.play_button)

        # Stop button
        self.stop_button = QPushButton()
        if style:
            self.stop_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.stop_button.setToolTip("Stop")
        self.controls_layout.addWidget(self.stop_button)

        # Position slider
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)
        self.controls_layout.addWidget(self.position_slider)

        # Position label
        self.position_label = QLabel("00:00 / 00:00")
        self.controls_layout.addWidget(self.position_label)

        # Volume layout
        volume_layout = QHBoxLayout()

        # Volume icon
        self.volume_button = QPushButton()
        if style:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
        volume_layout.addWidget(self.volume_button)

        # Volume slider
        self.volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)  # Default volume
        self.audio_output.setVolume(1.0)
        volume_layout.addWidget(self.volume_slider)

        self.controls_layout.addLayout(volume_layout)
        self.main_layout.addLayout(self.controls_layout)

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Create menu bar
        self.create_menu_bar()

        # Create toolbar
        self.create_toolbar()

        # Set strong focus policy for the main window
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Set focus to main window
        self.setFocus()

    def create_menu_bar(self) -> None:
        """Create the application menu bar."""
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

        # Media player connections
        self.media_player.playbackStateChanged.connect(self.playback_state_changed)
        self.media_player.positionChanged.connect(self.position_changed)
        self.media_player.durationChanged.connect(self.duration_changed)
        self.media_player.errorOccurred.connect(self.handle_error)

        # Slider connections
        self.position_slider.sliderMoved.connect(self.set_position)
        self.volume_slider.valueChanged.connect(self.set_volume)

        self.media_player.mediaStatusChanged.connect(self.media_status_changed)

    def media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        status_messages = {
            QMediaPlayer.MediaStatus.NoMedia: "No media",
            QMediaPlayer.MediaStatus.LoadingMedia: "Loading media...",
            QMediaPlayer.MediaStatus.LoadedMedia: "Media loaded",
            QMediaPlayer.MediaStatus.StalledMedia: "Media stalled",
            QMediaPlayer.MediaStatus.BufferingMedia: "Buffering...",
            QMediaPlayer.MediaStatus.BufferedMedia: "Media buffered",
            QMediaPlayer.MediaStatus.EndOfMedia: "End of media",
            QMediaPlayer.MediaStatus.InvalidMedia: "Invalid media",
        }

        if status in status_messages:
            print(f"Media status: {status_messages[status]}")  # Debug info

    def open_file(self) -> None:
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Media File",
                str(Path.home()),
                "Media Files (*.mp3 *.mp4 *.avi *.mkv *.wav *.flac *.ogg *.webm *.mov *.m4a *.3gp);;All Files (*)"
            )

            if file_path:
                file_url = QUrl.fromLocalFile(file_path)
                self.media_player.setSource(file_url)

                if self.media_player.source().isEmpty():
                    self.status_bar.showMessage(f"Error: Could not load {Path(file_path).name}")
                else:
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

    def toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        try:
            if self.media_player.source().isEmpty():
                self.status_bar.showMessage("No media file loaded")
                return

            self.media_player.play()
            self.update_play_button_state()
            self.setFocus()

        except Exception as e:
            self.status_bar.showMessage(f"Playback error: {str(e)}")

    def update_play_button_state(self) -> None:
        """Update play button based on current state."""
        style = self.style()
        if not style:
            return

        state = self.media_player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.play_button.setToolTip("Pause")
        else:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_button.setToolTip("Play")

    def pause(self) -> None:
        # Store current position before pausing
        self.current_position = self.media_player.position()
        self.media_player.pause()

        style = self.style()
        if style:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Play")

    def stop(self) -> None:
        self.current_position = 0
        self.media_player.stop()

        style = self.style()
        if style:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Play")

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
            self.set_position(self.media_player.duration())
        else:
            super().keyPressEvent(event)

    def skip_forward(self) -> None:
        current_position = self.media_player.position()
        duration = self.media_player.duration()
        if duration > 0:  # Make sure we have media loaded
            new_position = min(current_position + 5000, duration)
            self.set_position(new_position)
            print(f"Skipped forward to {new_position}ms")

    def skip_backward(self) -> None:
        """Skip backward 10 seconds."""
        current_position = self.media_player.position()
        new_position = max(0, current_position - 5000)
        self.set_position(new_position)
        print(f"Skipped backward to {new_position}ms")

    def playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        """Handle playback state changes."""
        style = self.style()
        if not style:
            return

        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
            self.play_button.setToolTip("Pause")
            self.status_bar.showMessage("Playing")
            # Set focus to main window for keyboard shortcuts
            self.setFocus()
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_button.setToolTip("Play")
            self.status_bar.showMessage("Paused")
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
            self.play_button.setToolTip("Play")
            self.status_bar.showMessage("Stopped")

    def position_changed(self, position: int) -> None:
        """Update the position slider and label."""
        # Store current position for proper resuming
        self.current_position = position

        # Update slider without triggering events
        self.position_slider.blockSignals(True)
        self.position_slider.setValue(position)
        self.position_slider.blockSignals(False)

        # Update position label
        current_time = QTime(0, 0).addMSecs(position)
        total_time = QTime(0, 0).addMSecs(self.media_player.duration())
        time_format = "hh:mm:ss" if self.media_player.duration() > 3600000 else "mm:ss"
        self.position_label.setText(
            f"{current_time.toString(time_format)} / {total_time.toString(time_format)}"
        )

    def duration_changed(self, duration: int) -> None:
        """Update the position slider range."""
        self.position_slider.setRange(0, duration)

        # Update position label
        current_time = QTime(0, 0).addMSecs(self.media_player.position())
        total_time = QTime(0, 0).addMSecs(duration)
        time_format = "hh:mm:ss" if duration > 3600000 else "mm:ss"
        self.position_label.setText(
            f"{current_time.toString(time_format)} / {total_time.toString(time_format)}"
        )

    def set_position(self, position: int) -> None:
        """Set the playback position."""
        current_state = self.media_player.playbackState()
        is_playing = (current_state == QMediaPlayer.PlaybackState.PlayingState)

        # If currently playing, pause first for better sync
        if is_playing:
            self.media_player.pause()

        # Set the position
        self.media_player.setPosition(position)
        self.current_position = position

        # Resume if it was playing
        if is_playing:
            self.media_player.play()

    def set_volume(self, volume: int) -> None:
        """Set the audio volume."""
        self.audio_output.setVolume(volume / 100.0)

        style = self.style()
        if not style:
            return

        # Update volume icon based on level
        if volume <= 0:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))
        else:
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))

    def toggle_mute(self) -> None:
        """Toggle audio mute state."""
        style = self.style()
        if not style:
            return

        if self.audio_output.isMuted():
            self.audio_output.setMuted(False)
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolume))
            self.volume_slider.setValue(int(self.audio_output.volume() * 100))
        else:
            self.audio_output.setMuted(True)
            self.volume_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaVolumeMuted))

    def handle_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        if error != QMediaPlayer.Error.NoError:
            self.status_bar.showMessage(f"Error: {error_string}")

    def about(self) -> None:
        self.status_bar.showMessage("Media Player - A PyQt6 based media player application")

    def increase_volume(self) -> None:
        current_volume = self.volume_slider.value()
        new_volume = min(100, current_volume + 5)
        self.volume_slider.setValue(new_volume)
        self.status_bar.showMessage(f"Volume: {new_volume}%", 2000)

    def decrease_volume(self) -> None:
        current_volume = self.volume_slider.value()
        new_volume = max(0, current_volume - 5)
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
        current_source = self.media_player.source()
        if not current_source.isEmpty() and current_source.isLocalFile():
            file_path = Path(current_source.toLocalFile())
            if file_path not in self.playlist:
                self.playlist.append(file_path)
                self.current_playlist_index = len(self.playlist) - 1
                self.status_bar.showMessage(f"Added to playlist: {file_path.name}")

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
            self.media_player.setSource(QUrl.fromLocalFile(str(file_path)))
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

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.is_fullscreen:
            self.exit_fullscreen()

        self.media_player.stop()
        self.save_settings()
        event.accept()