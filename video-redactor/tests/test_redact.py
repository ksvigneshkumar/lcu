import unittest
import os
from src.rules import load_rules
from src.redact import Redactor

class TestRedactor(unittest.TestCase):
    def setUp(self):
        # Create a dummy rules.json
        self.rules_file = "test_rules.json"
        with open(self.rules_file, "w") as f:
            f.write('{"types": ["PERSON", "PHONE_NUMBER"], "words": ["SecretProject"], "regex": ["ID-\\\\d{4}"], "replacement_style": "tag"}')
            
    def tearDown(self):
        if os.path.exists(self.rules_file):
            os.remove(self.rules_file)

    def test_load_rules(self):
        rules = load_rules(self.rules_file)
        self.assertIn("PERSON", rules["types"])
        self.assertIn("SecretProject", rules["words"])
        self.assertIn("ID-\\d{4}", rules["regex"])
        self.assertEqual(rules["replacement_style"], "tag")

    def test_redaction(self):
        rules = load_rules(self.rules_file)
        redactor = Redactor(rules)
        
        text = "Hello, my name is John Doe. Call me at 555-1234. We are working on SecretProject with ID-9999."
        redacted_text, redactions = redactor.redact_segment(text)
        
        self.assertIn("[PERSON]", redacted_text)
        self.assertNotIn("John Doe", redacted_text)
        
        self.assertIn("[PHONE_NUMBER]", redacted_text)
        self.assertNotIn("555-1234", redacted_text)
        
        self.assertIn("[EXACT_WORD]", redacted_text)
        self.assertNotIn("SecretProject", redacted_text)
        
        self.assertIn("[CUSTOM_REGEX]", redacted_text)
        self.assertNotIn("ID-9999", redacted_text)

if __name__ == '__main__':
    unittest.main()
