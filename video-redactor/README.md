# Video Redactor

Take a video (recorded file, or a live stream URL), convert the speech to text, read a rules file that says what must be redacted, redact the transcript, and write the result to one output file.

## Requirements

1. Python 3.8+
2. FFmpeg installed on your system and available in PATH.
3. Microsoft Presidio and Faster Whisper.

## Installation

1. Install FFmpeg:
   - Windows: `winget install ffmpeg` or download from official site.
   - Linux: `sudo apt install ffmpeg`
   - macOS: `brew install ffmpeg`

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download the spaCy model required for Presidio:
   ```bash
   python -m spacy download en_core_web_lg
   ```

## Usage

```bash
# Process a local file
python main.py --input meeting.mp4 --rules rules.txt

# Process a live stream (e.g. RTSP camera) for 120 seconds
python main.py --input rtsp://camera-url/stream --duration 120 --rules rules.json
```

## Outputs

- `output/redacted_transcript.txt`: The text file with sensitive information replaced by tags (e.g., `[PERSON]`).
- `output/redaction_report.json`: A summary report containing redaction counts and timestamps. It does **not** contain the original sensitive data.

## Security Warning

**Automatic redaction is not 100% accurate.** The output should always be reviewed by a human before sharing. The raw transcript and original sensitive values are never printed or logged to ensure data safety. However, AI models may miss some entities. To improve accuracy for your specific use case, add known exact words or custom regexes to your rules file.
