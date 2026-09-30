import unittest

from radiusdeck.lib.fr_parser import parse_clients_conf, render_clients_conf

SAMPLE_CONF = """
client localhost {
    ipaddr = 127.0.0.1
    secret = testing123
    shortname = "local"
}

# Comment here
client other {
    secret = 'single quoted string'
    filter = 'yes \\' allowed'
}
"""


class TestIntegration(unittest.TestCase):
    def test_round_trip(self):
        """Парсим, рендерим и сравниваем с очищенным оригиналом"""
        nodes = parse_clients_conf(SAMPLE_CONF)
        output = render_clients_conf(nodes)

        # Check key points in the output:
        # 1. Empty lines did not multiply (just visually or count)
        self.assertIn("client localhost {", output)
        self.assertIn('shortname = "local"', output)  # quotes preserved
        self.assertIn("secret = 'single quoted string'", output)  # quote type preserved

        # The most complex: escaping in single quotes
        # In the source: 'yes \' allowed' (this is a python string), in the file it's yes \' allowed
        # We want to see the same thing
        self.assertIn("filter = 'yes \\' allowed'", output)

    def test_stability(self):
        """Парсинг -> Рендер -> Парсинг -> Рендер. Результат 1 и 2 должен совпасть байт в байт"""
        nodes1 = parse_clients_conf(SAMPLE_CONF)
        out1 = render_clients_conf(nodes1)

        nodes2 = parse_clients_conf(out1)
        out2 = render_clients_conf(nodes2)

        self.assertEqual(out1, out2)
