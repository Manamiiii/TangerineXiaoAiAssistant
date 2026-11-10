import unittest

from scripts.check_desktop_entry import literal_version


class DeliveryTests(unittest.TestCase):
    def test_reads_literal_without_executing_application_code(self):
        code = compile('__version__ = "0.4.2"\nraise RuntimeError("must never execute")',
                       'fixture', 'exec')
        self.assertEqual(literal_version(code), '0.4.2')

    def test_refuses_computed_or_missing_version(self):
        for source in ('__version__ = str(42)', 'other = "0.4.2"', '__version__ = 42'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                literal_version(compile(source, 'fixture', 'exec'))
