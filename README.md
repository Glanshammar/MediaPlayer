# Media Player

A simple media player application built with PyQt6 that supports various audio and video formats.

## Features

- Play, pause, and stop media playback
- Volume control and mute toggle
- Media position seeking
- Support for various media formats (MP3, MP4, AVI, MKV, WAV, FLAC, OGG, WebM)
- True fullscreen mode (toggle with 'F' key, exit with 'F' or 'Escape' key)
- Simple and clean user interface

## Requirements

- Python 3.6 or higher
- PyQt6

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/MediaPlayer.git
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

### Controls

- Click "Open" button or press Ctrl+O to open a media file
- Use the play/pause button to control playback
- Use the slider to seek through the media
- Adjust volume using the volume slider
- Press F to toggle fullscreen mode
- Press Escape to exit fullscreen mode
- Press Right Arrow to skip forward 10 seconds
- Press Left Arrow to skip backward 10 seconds
- Press Ctrl+Q to exit the application

## License

This project is open source and available under the MIT License.

## Contributing

Contributions, issues, and feature requests are welcome! 