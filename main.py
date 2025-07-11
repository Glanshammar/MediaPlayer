#!/usr/bin/env python3
"""
MediaPlayer - A simple media player application built with PyQt6
"""

import sys
import time
from pathlib import Path
from typing import Optional, Union, cast

from PyQt6.QtCore import QUrl, Qt, QTime, QEvent, QObject
from PyQt6.QtGui import QIcon, QAction, QKeyEvent
from PyQt6.QtWidgets import (
    QApplication, 
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
    QMenu,
    QMenuBar
)
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaFormat
from PyQt6.QtMultimediaWidgets import QVideoWidget


class MediaPlayer(QMainWindow):
    """Main window for the media player application."""
    
    def __init__(self) -> None:
        """Initialize the media player window."""
        super().__init__()
        
        self.setWindowTitle("Media Player")
        self.setGeometry(100, 100, 800, 600)
        
        # Track fullscreen state
        self.is_fullscreen = False
        
        # Track current position for proper resume
        self.current_position = 0
        
        # Create media player with proper settings
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        
        # Set the audio buffer size for better sync
        # self.audio_output.setBufferSize(2048)  # Larger buffer for smoother playback
        
        # Connect error handling
        self.media_player.errorOccurred.connect(self.handle_error)
        
        # Create video widget
        self.video_widget = QVideoWidget()
        self.video_widget.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.media_player.setVideoOutput(self.video_widget)
        
        # Install event filter on video widget to handle double clicks
        self.video_widget.installEventFilter(self)
        
        # Create UI elements
        self.setup_ui()
        
        # Setup connections
        self.setup_connections()
        
        # Install event filter to capture all key events
        self.installEventFilter(self)

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
        self.volume_slider.setValue(70)  # Default volume
        self.audio_output.setVolume(0.7)
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
        skip_forward_action = QAction("Skip &Forward 10 Seconds", self)
        skip_forward_action.setShortcut("Right")
        skip_forward_action.triggered.connect(self.skip_forward)
        playback_menu.addAction(skip_forward_action)
        
        # Skip backward action
        skip_backward_action = QAction("Skip &Backward 10 Seconds", self)
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
        
        # Add fullscreen button to toolbar
        fullscreen_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarMaxButton), "Fullscreen", self)
        fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.toolbar.addAction(fullscreen_action)
        
        # Add skip backward button
        skip_backward_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipBackward), "Skip Backward", self)
        skip_backward_action.triggered.connect(self.skip_backward)
        self.toolbar.addAction(skip_backward_action)
        
        # Add skip forward button
        skip_forward_action = QAction(style.standardIcon(QStyle.StandardPixmap.SP_MediaSkipForward), "Skip Forward", self)
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
        
        # Slider connections
        self.position_slider.sliderMoved.connect(self.set_position)
        self.volume_slider.valueChanged.connect(self.set_volume)

    def open_file(self) -> None:
        """Open a media file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Media File",
            str(Path.home()),
            "Media Files (*.mp3 *.mp4 *.avi *.mkv *.wav *.flac *.ogg *.webm);;All Files (*)"
        )
        
        if file_path:
            self.media_player.setSource(QUrl.fromLocalFile(file_path))
            self.status_bar.showMessage(f"Loaded: {Path(file_path).name}")
            self.play()

    def toggle_playback(self) -> None:
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """Start playing the media."""
        current_state = self.media_player.playbackState()
        
        # If we're resuming from a pause
        if current_state == QMediaPlayer.PlaybackState.PausedState:
            # Store current position before resuming
            position = self.media_player.position()
            
            # Reset to slightly before current position to ensure proper sync
            if position > 100:  # Don't do this if we're near the start
                # Stop first to reset buffers
                self.media_player.stop()
                
                # Small delay to ensure proper reset
                QApplication.processEvents()
                
                # Set position and play
                self.media_player.setPosition(position)
                
        # Play the media
        self.media_player.play()
        
        style = self.style()
        if style:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.play_button.setToolTip("Pause")
        
        # Set focus to main window for keyboard shortcuts
        self.setFocus()

    def pause(self) -> None:
        """Pause the media playback."""
        # Store current position before pausing
        self.current_position = self.media_player.position()
        self.media_player.pause()
        
        style = self.style()
        if style:
            self.play_button.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.play_button.setToolTip("Play")

    def stop(self) -> None:
        """Stop the media playback."""
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
        # Handle double clicks on video widget
        elif event.type() == QEvent.Type.MouseButtonDblClick and obj is self.video_widget:
            self.toggle_fullscreen()
            return True
                
        # Let parent class handle the rest
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events."""
        if event.key() == Qt.Key.Key_F:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape and self.is_fullscreen:
            self.exit_fullscreen()
        elif event.key() == Qt.Key.Key_Right:
            self.skip_forward()
            self.status_bar.showMessage("Skipped forward 10 seconds", 2000)
        elif event.key() == Qt.Key.Key_Left:
            self.skip_backward()
            self.status_bar.showMessage("Skipped backward 10 seconds", 2000)
        elif event.key() == Qt.Key.Key_Space:
            self.toggle_playback()
            self.status_bar.showMessage("Play/Pause toggled", 2000)
        else:
            super().keyPressEvent(event)
            
    def skip_forward(self) -> None:
        """Skip forward 10 seconds."""
        current_position = self.media_player.position()
        duration = self.media_player.duration()
        if duration > 0:  # Make sure we have media loaded
            new_position = min(current_position + 10000, duration)
            self.set_position(new_position)
            print(f"Skipped forward to {new_position}ms")
        
    def skip_backward(self) -> None:
        """Skip backward 10 seconds."""
        current_position = self.media_player.position()
        new_position = max(0, current_position - 10000)
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
        
        # Resume if was playing
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
        """Handle media player errors."""
        if error != QMediaPlayer.Error.NoError:
            self.status_bar.showMessage(f"Error: {error_string}")

    def about(self) -> None:
        """Show about dialog."""
        self.status_bar.showMessage("Media Player - A PyQt6 based media player application")
        
    def closeEvent(self, event) -> None:
        """Handle window close event."""
        # Exit fullscreen if active
        if self.is_fullscreen:
            self.exit_fullscreen()
            
        # Stop playback before closing
        self.media_player.stop()
        event.accept()


if __name__ == "__main__":
    """Main application entry point."""
    try:
        app = QApplication(sys.argv)
        
        # Set application style
        app.setStyle('Fusion')
        
        # Create and show the media player
        player = MediaPlayer()
        player.show()
        
        sys.exit(app.exec())
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)