import argparse
import logging
import sys
import os

# --- Monkey patch for PyAV >= 12.0.0 with faster-whisper ---
import av
original_av_open = av.open
def patched_av_open(*args, **kwargs):
    kwargs.pop('metadata_errors', None)
    return original_av_open(*args, **kwargs)
av.open = patched_av_open
# -----------------------------------------------------------

from src.ingest import extract_audio
from src.transcribe import transcribe_audio

from src.rules import load_rules
from src.redact import Redactor
from src.output import write_outputs

def main():
    parser = argparse.ArgumentParser(description="Video Redactor - convert speech to text and redact sensitive information.")
    parser.add_argument("--input", required=True, help="Video source (local file path or live stream URL)")
    parser.add_argument("--rules", default="rules.txt", help="Rules file (.txt or .json)")
    parser.add_argument("--output", default="output/redacted_transcript.txt", help="Path for the output transcript")
    parser.add_argument("--duration", type=int, default=60, help="Duration to record for live stream URL (in seconds)")
    parser.add_argument("--keep-temp", action="store_true", help="Keep the temporary audio file")
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Read API keys/envs if needed from .env (optional if using external APIs, though everything here is local)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass # python-dotenv not strictly required if no keys are used
    
    # Validation
    if not os.path.exists(args.rules):
        logging.error(f"Rules file not found: {args.rules}")
        sys.exit(1)
        
    try:
        rules = load_rules(args.rules)
        logging.info(f"Loaded rules successfully.")
    except Exception as e:
        logging.error(f"Error loading rules: {e}")
        sys.exit(1)
        
    audio_path = None
    try:
        # 1. Ingest
        audio_path = extract_audio(args.input, duration=args.duration)
        
        # 2. Transcribe
        segments = transcribe_audio(audio_path)
        
        # 3. Redact
        redactor = Redactor(rules)
        
        redacted_segments = []
        for seg in segments:
            redacted_text, redactions = redactor.redact_segment(seg['text'])
            redacted_segments.append({
                "start": seg['start'],
                "end": seg['end'],
                "text": redacted_text,
                "redactions": redactions
            })
            
        # 4. Output
        output_dir = os.path.dirname(args.output)
        if output_dir:
            report_path = os.path.join(output_dir, "redaction_report.json")
        else:
            report_path = "redaction_report.json"
            
        write_outputs(redacted_segments, rules, args.output, report_path)
        
        logging.info("Redaction pipeline completed successfully.")
        
    except Exception as e:
        logging.error(f"Pipeline failed: {e}")
        sys.exit(1)
    finally:
        # Cleanup
        if audio_path and os.path.exists(audio_path) and not args.keep_temp:
            logging.info(f"Cleaning up temporary file {audio_path}")
            try:
                os.remove(audio_path)
            except Exception as e:
                logging.error(f"Failed to remove temporary file: {e}")

if __name__ == "__main__":
    main()
