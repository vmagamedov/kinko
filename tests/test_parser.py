from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from funcparserlib.parser import NoParseError

from kinko import nodes as N
from kinko.parser import parser
from kinko.tokenizer import tokenize


def node_eq(self, other):
    if type(self) is not type(other):
        return
    d1 = dict(self.__dict__)
    d1.pop('location', None)
    d2 = dict(other.__dict__)
    d2.pop('location', None)
    return d1 == d1


def node_ne(self, other):
    return not self.__eq__(other)


class TestParser(TestCase):

    def setUp(self):
        self.node_patcher = patch.multiple(N.Node, __eq__=node_eq,
                                           __ne__=node_ne)
        self.node_patcher.start()

    def tearDown(self):
        self.node_patcher.stop()

    def parse(self, text):
        tokens = list(tokenize(text))
        try:
            return parser().parse(tokens)
        except NoParseError as e:
            print(e.msg, tokens[e.state.pos], tokens[e.state.max])
            print(tokens)
            raise AssertionError("Parse failed: " + e.msg)

    def testSimple(self):
        self.assertEqual(self.parse('div "text"'), [
            N.Tuple(N.Symbol('div'), [N.String("text")])
        ])

    def testIndent(self):
        self.assertEqual(self.parse('div\n "text"'), [
            N.Tuple(N.Symbol('div'), [N.String("text")])
        ])

    def testNested(self):
        self.assertEqual(self.parse("""div "text"
            div 12
        """), [
            N.Tuple(N.Symbol('div'), [
                N.String("text"),
                N.Tuple(N.Symbol("div"), [N.Number(12)]),
                ])
        ])

    def testKeyword(self):
        self.assertEqual(self.parse('div :class "red" "text"'), [
            N.Tuple(N.Symbol('div'), [
                N.KeywordPair(N.Keyword("class"), N.String("red")),
                N.String("text"),
            ])
        ])
