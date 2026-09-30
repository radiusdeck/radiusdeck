import unittest

from radiusdeck.lib.fr_parser.ast import Assignment
from radiusdeck.lib.fr_parser.renderer import _render_value, render_clients_conf


class TestRenderer(unittest.TestCase):
    def test_render_value_auto_quotes(self):
        self.assertEqual(_render_value("simple", None), "simple")
        self.assertEqual(_render_value("with space", None), '"with space"')
        self.assertEqual(_render_value("123", None), "123")
        self.assertEqual(_render_value("123456", None), "123456")

    def test_render_forced_quotes(self):
        # Even if quotes are not needed, but quote_char is set
        self.assertEqual(_render_value("simple", '"'), '"simple"')
        self.assertEqual(_render_value("simple", "'"), "'simple'")

    def test_escaping_single_quotes(self):
        val = "It's allowed"
        # Expect: 'It\'s allowed'
        rendered = _render_value(val, "'")
        self.assertEqual(rendered, "'It\\'s allowed'")

    def test_escaping_double_quotes(self):
        val = 'Say "Hello"'
        # Expect: "Say \"Hello\""
        rendered = _render_value(val, '"')
        self.assertEqual(rendered, '"Say \\"Hello\\""')

    def test_render_full_assignment(self):
        node = Assignment(key="filter", value="yes ' ok", quote_char="'")
        res = render_clients_conf([node])
        self.assertEqual(res, "filter = 'yes \\' ok'\n")
