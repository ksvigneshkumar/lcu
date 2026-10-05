import json
import os
import logging
from typing import List, Dict, Any

def format_timestamp(seconds: float) -> str:
    """Formats seconds to HH:MM:SS format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def write_outputs(segments: List[Dict[str, Any]], rules_used: Dict[str, Any], output_text_path: str, output_report_path: str):
    """
    Writes the redacted transcript and the redaction report.
    """
    # Ensure directory exists if not empty path
    if os.path.dirname(output_text_path):
        os.makedirs(os.path.dirname(output_text_path), exist_ok=True)
    
    total_redactions = 0
    count_per_type = {}
    report_redactions = []
    
    logging.info(f"Writing redacted transcript to {output_text_path}...")
    with open(output_text_path, 'w', encoding='utf-8') as f:
        for seg in segments:
            start_str = format_timestamp(seg['start'])
            end_str = format_timestamp(seg['end'])
            # Writing the line format requested
            f.write(f"[{start_str} - {end_str}] {seg['text']}\n")
            
            for red in seg.get('redactions', []):
                total_redactions += 1
                entity_type = red['entity_type']
                count_per_type[entity_type] = count_per_type.get(entity_type, 0) + 1
                report_redactions.append({
                    "start_time_seconds": seg['start'],
                    "end_time_seconds": seg['end'],
                    "entity_type": entity_type,
                    "score": red['score']
                })

    logging.info(f"Writing redaction report to {output_report_path}...")
    report = {
        "total_redactions": total_redactions,
        "count_per_entity_type": count_per_type,
        "rules_used": rules_used,
        "redactions": report_redactions
    }
    
    if os.path.dirname(output_report_path):
        os.makedirs(os.path.dirname(output_report_path), exist_ok=True)
    with open(output_report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4)
