import subprocess
import os
import uuid
import logging

def extract_audio(input_source: str, duration: int = 60, output_dir: str = "output") -> str:
    """
    Extracts audio from a local file or records from a live stream URL.
    Saves the extracted audio to a temporary 16kHz mono WAV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    temp_filename = f"temp_audio_{uuid.uuid4().hex}.wav"
    output_path = os.path.join(output_dir, temp_filename)
    
    is_live = input_source.startswith(("rtsp://", "http://", "https://"))
    
    command = [
        "ffmpeg",
        "-y", # Overwrite output files without asking
        "-i", input_source,
        "-vn", # Disable video recording
        "-acodec", "pcm_s16le", # PCM signed 16-bit little-endian
        "-ar", "16000", # 16kHz sampling rate
        "-ac", "1", # Mono
    ]
    
    if is_live:
        logging.info(f"Live stream detected. Recording for {duration} seconds...")
        command.extend(["-t", str(duration)])
    else:
        logging.info(f"Local file detected. Extracting audio...")

    command.append(output_path)
    
    try:
        subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        logging.info(f"Audio extracted to {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        error_msg = f"ffmpeg error extracting audio: {e.stderr.decode('utf-8', errors='ignore')}"
        logging.error(error_msg)
        raise RuntimeError(error_msg) from e
