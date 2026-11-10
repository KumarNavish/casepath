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


class ReadingAndMiningVoiceTests(unittest.TestCase):
    def test_photo_descriptions_follow_the_configured_language(self):
        from casepath.read.reading import PHOTO_INSTRUCTIONS, photo_instructions
        self.assertIn("for a case handler, in German with Swiss\nspelling (ss, not ß): begin with [Foto]", photo_instructions())
        configured = photo_instructions({"writing": "in English"})
        self.assertIn("for a case handler, in English: begin with [Foto]", configured)
        self.assertNotIn("German", configured)
        self.assertIn("{writing}", PHOTO_INSTRUCTIONS)

    def test_mining_names_the_configured_organisation(self):
        from casepath.process import mining
        self.assertIn("Protekta", mining.actors())
        self.assertEqual(mining.actors("Example Insurance")[2], "Example Insurance")
        self.assertIn("Then list Protekta's own actions", mining.COURSE_INSTRUCTIONS.format(organisation=mining.DEFAULT_ORGANISATION))
        self.assertNotIn("Protekta", mining.COURSE_INSTRUCTIONS + mining.GROUP_INSTRUCTIONS)
