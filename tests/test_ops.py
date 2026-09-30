import unittest

from radiusdeck.lib.fr_parser.ast import Assignment, Block
from radiusdeck.lib.fr_parser.ops import find_client, set_assignment, upsert_client


class TestOps(unittest.TestCase):
    def setUp(self):
        self.nodes = []

    def test_upsert_new(self):
        upsert_client(self.nodes, "nas1", {"secret": "pass"})
        blk = find_client(self.nodes, "nas1")
        assert blk is not None
        self.assertIsNotNone(blk)
        child = blk.children[0]
        assert isinstance(child, Assignment)
        self.assertEqual(child.key, "secret")
        self.assertEqual(child.value, "pass")

    def test_upsert_update(self):
        # Create manually
        self.nodes.append(Block("client", "nas1"))
        # Update
        upsert_client(self.nodes, "nas1", {"shortname": "n1"})

        blk = find_client(self.nodes, "nas1")
        assert blk is not None
        child = blk.children[0]
        assert isinstance(child, Assignment)
        self.assertEqual(child.key, "shortname")

    def test_set_assignment_preserves_quotes(self):
        blk = Block("client", "test")
        set_assignment(blk, "k", "val", quoted="'")

        # Update value, quoted=None -> single quotes should be preserved
        set_assignment(blk, "k", "new_val")

        child = blk.children[0]
        assert isinstance(child, Assignment)

        self.assertEqual(child.quote_char, "'")
        self.assertEqual(child.value, "new_val")

    def test_set_assignment_force_quotes(self):
        blk = Block("client", "test")
        set_assignment(blk, "k", "val", quoted=True)  # Double quotes
        child = blk.children[0]
        assert isinstance(child, Assignment)
        self.assertEqual(child.quote_char, '"')
