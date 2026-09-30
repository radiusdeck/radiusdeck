import unittest

from radiusdeck.lib.fr_parser.tokens import tokenize


class TestTokenizer(unittest.TestCase):
    def test_simple_assignment(self):
        text = "key = value"
        toks = tokenize(text)
        types = [t.typ for t in toks]
        self.assertEqual(types, ["IDENT", "EQUAL", "IDENT", "EOF"])
        self.assertEqual(toks[0].val, "key")
        self.assertEqual(toks[2].val, "value")

    def test_strings_double(self):
        text = 'secret = "my secret"'
        toks = tokenize(text)
        self.assertEqual(toks[2].typ, "STRING")
        self.assertEqual(toks[2].val, "my secret")

    def test_strings_single(self):
        text = "filter = 'raw string'"
        toks = tokenize(text)
        self.assertEqual(toks[2].typ, "SSTRING")
        self.assertEqual(toks[2].val, "raw string")

    def test_escaping_single(self):
        # Input: 'It\'s me'
        text = "val = 'It\\'s me'"
        toks = tokenize(text)
        self.assertEqual(toks[2].typ, "SSTRING")
        # The tokenizer should eat the backslash
        self.assertEqual(toks[2].val, "It's me")

    def test_block_chars(self):
        text = "client {"
        toks = tokenize(text)
        self.assertEqual(toks[0].typ, "IDENT")
        self.assertEqual(toks[1].typ, "LBRACE")
