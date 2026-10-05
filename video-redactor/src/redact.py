from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
import logging
from typing import Dict, Any, Tuple, List
import re

class Redactor:
    def __init__(self, rules: Dict[str, Any]):
        self.rules = rules
        self.replacement_style = rules.get("replacement_style", "tag")
        
        logging.info("Initializing Presidio Analyzer Engine with en_core_web_lg...")
        
        # Configure to use en_core_web_lg as requested
        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}]
        })
        nlp_engine = provider.create_engine()
        self.analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        self.anonymizer = AnonymizerEngine()
        
        self.entities = rules.get("types", [])
        
        # Add exact words recognizer
        if rules.get("words"):
            # Escape words to prevent regex errors and use word boundaries
            escaped_words = [re.escape(w) for w in rules["words"]]
            regex_str = r'\b(?:' + '|'.join(escaped_words) + r')\b'
            # Case insensitive is default in Presidio PatternRecognizer for regex but we can be explicit
            word_patterns = [Pattern(name="exact_word", regex=regex_str, score=1.0)]
            word_recognizer = PatternRecognizer(supported_entity="EXACT_WORD", patterns=word_patterns)
            self.analyzer.registry.add_recognizer(word_recognizer)
            self.entities.append("EXACT_WORD")
            
        # Add regex recognizer
        if rules.get("regex"):
            regex_patterns = [Pattern(name=f"regex_{i}", regex=pattern, score=1.0) for i, pattern in enumerate(rules["regex"])]
            if regex_patterns:
                regex_recognizer = PatternRecognizer(supported_entity="CUSTOM_REGEX", patterns=regex_patterns)
                self.analyzer.registry.add_recognizer(regex_recognizer)
                self.entities.append("CUSTOM_REGEX")

    def redact_segment(self, text: str) -> Tuple[str, List[Dict[str, Any]]]:
        if not text.strip():
            return text, []

        # Analyze
        results = self.analyzer.analyze(text=text, entities=self.entities, language='en')
        
        # Prepare operators for anonymization
        operators = {}
        if self.replacement_style == "mask":
            for entity in self.entities:
                operators[entity] = OperatorConfig("replace", {"new_value": "*****"})
        else:
            for entity in self.entities:
                # If "tag", replace with [<ENTITY_TYPE>]
                operators[entity] = OperatorConfig("replace", {"new_value": f"[{entity}]"})
                
        # Anonymize
        anonymized_result = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            operators=operators
        )
        
        # Prepare report data
        redactions = []
        for result in results:
            redactions.append({
                "entity_type": result.entity_type,
                "start": result.start,
                "end": result.end,
                "score": result.score
            })
            
        return anonymized_result.text, redactions
