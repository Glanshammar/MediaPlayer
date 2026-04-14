# Media Player
A simple media player application built with PyQt6 that supports various audio and video formats.

## Features
- Play, pause, and stop media playback
- Volume control and mute toggle
- Media position seeking
- Support for various media formats (MP3, MP4, AVI, MKV, WAV, FLAC, OGG, WebM)
- True fullscreen mode (toggle with 'F' key, exit with 'F' or 'Escape' key)
- Simple and clean user interface
- Download videos.
- Two sidebars
  - Left; A list of all videos and playlists. You can add videos to your playlists and filter the sidebar list to it.
  - Right; A list of all the video chapters of that video. Click the chapters to go there.

## Requirements
- Python 3.14 or higher

## Installation
1. Clone this repository:
   ```
   git clone https://github.com/Glanshammar/MediaPlayer.git
   cd MediaPlayer
   ```

2. Create a virtual environment (optional but recommended):
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage
Run the application with:

```
python main.py
```

Build the application with:
```
pyinstaller --noconsole --onefile --name MediaPlayer --icon=app_icon.ico --add-data "app_icon.png;." main.py
```

### Controls
- Double-Click the video in the sidebar to play it
- Use the play/pause button to control playback
- Use the slider to seek through the media
- Adjust volume using the volume slider, or press the left and right arrow buttons
- Press F to toggle fullscreen mode
- Press F or Escape to exit fullscreen mode
- Press Right Arrow to skip forward 5 seconds
- Press Left Arrow to skip backward 5 seconds
- Press Ctrl+Q to exit the application

## License
This project is open source and available under the MIT License.

## Contributing
Contributions, issues, and feature requests are welcome! 