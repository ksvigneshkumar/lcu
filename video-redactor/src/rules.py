import json
import os
from typing import Dict, Any

def load_rules(file_path: str) -> Dict[str, Any]:
    """
    Loads and validates the rules file (.txt or .json).
    Returns a dictionary structured as:
    {
        "words": [],
        "types": [],
        "regex": [],
        "replacement_style": "tag" # or "mask"
    }
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Rules file not found: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    rules = {
        "words": [],
        "types": [],
        "regex": [],
        "replacement_style": "tag"
    }
    
    if ext == ".json":
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                rules["words"] = data.get("words", [])
                rules["types"] = data.get("types", [])
                rules["regex"] = data.get("regex", [])
                rules["replacement_style"] = data.get("replacement_style", "tag")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in rules file: {e}")
    elif ext == ".txt":
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("type:"):
                    rules["types"].append(line[5:].strip())
                elif line.startswith("regex:"):
                    rules["regex"].append(line[6:].strip())
                else:
                    rules["words"].append(line)
    else:
        raise ValueError(f"Unsupported rules file format: {ext}. Use .txt or .json")
        
    if rules["replacement_style"] not in ["tag", "mask"]:
        raise ValueError("replacement_style must be 'tag' or 'mask'")
        
    return rules
