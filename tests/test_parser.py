import unittest

from radiusdeck.lib.fr_parser.ast import Assignment, Block
from radiusdeck.lib.fr_parser.parser import parse_clients_conf


class TestParser(unittest.TestCase):
    def test_simple_block(self):
        text = """client my-nas {
    secret = 123
}"""
        nodes = parse_clients_conf(text)
        self.assertEqual(len(nodes), 1)

        node = nodes[0]
        assert isinstance(node, Block)

        self.assertIsInstance(node, Block)
        self.assertEqual(node.name, "my-nas")

        # Check internals
        children = node.children
        self.assertEqual(len(children), 1)  # Should not have BlankLine!

        child = children[0]
        assert isinstance(child, Assignment)
        self.assertIsInstance(children[0], Assignment)

    def test_multiple_blocks_no_extra_newlines(self):
        # Test for the problem of duplicating empty lines
        text = """client A {
    ip = 1
}
client B {
    ip = 2
}"""
        nodes = parse_clients_conf(text)
        # Expect: Block(A), BlankLine, Block(B) - total 3 nodes
        # (or 2, if there is no empty line between them, but here there is a new line)

        # The tokenizer will issue NEWLINE between blocks, the parser should turn it into BlankLine.
        # But it should NOT add BlankLine right after '}' or before 'client' magically.
        self.assertEqual(len(nodes), 2)  # Without empty line between them in the source

    def test_quoted_assignment(self):
        text = "shortname = 'foo'"
        nodes = parse_clients_conf(text)
        assign = nodes[0]
        assert isinstance(assign, Assignment)
        self.assertEqual(assign.value, "foo")
        self.assertEqual(assign.quote_char, "'")
