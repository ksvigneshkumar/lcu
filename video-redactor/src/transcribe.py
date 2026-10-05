from faster_whisper import WhisperModel
import logging
from typing import List, Dict, Any

def transcribe_audio(audio_path: str, model_size: str = "small") -> List[Dict[str, Any]]:
    """
    Transcribes the audio file using faster-whisper.
    Returns a list of segments with start, end, and text.
    """
    logging.info(f"Loading Whisper model ({model_size})...")
    # Using compute_type="default" for broad compatibility
    model = WhisperModel(model_size, device="auto", compute_type="default")
    
    logging.info(f"Transcribing audio from {audio_path}...")
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=False
    )
    
    logging.info("Transcription completed.")
    
    result = []
    for segment in segments:
        result.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        })
    return result
