import unittest

from casepath.agents.team import common_instructions
from casepath.config import load_settings


class VoiceTests(unittest.TestCase):
    def test_the_default_is_the_earlier_fixed_text(self):
        text = common_instructions()
        self.assertIn("legal-protection cases for Protekta case handlers.", text)
        self.assertIn("in the language of the case files, usually German, with Swiss spelling (ss, not ß).", text)
        self.assertNotIn("{", text)

    def test_organisation_and_writing_language_are_configuration(self):
        text = common_instructions({"organisation": "the insurer's", "writing": "in English"})
        self.assertIn("legal-protection cases for the insurer's case handlers.", text)
        self.assertIn("drafts) in English.", text)
        self.assertNotIn("Protekta", text)
        settings = load_settings({"CASEPATH_ORGANISATION": "Example Insurance", "CASEPATH_WRITING_LANGUAGE": "in English"})
        self.assertEqual((settings.organisation, settings.writing_language), ("Example Insurance", "in English"))
        self.assertIsNone(load_settings({}).organisation)


if __name__ == "__main__":
    unittest.main()
