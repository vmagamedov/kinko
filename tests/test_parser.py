from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from funcparserlib.parser import NoParseError

from kinko.nodes import Node, Symbol, Tuple, String, Number, Keyword, Dict, List
from kinko.parser import parser
from kinko.tokenizer import tokenize


def node_eq(self, other):
    if type(self) is not type(other):
        return
    d1 = dict(self.__dict__)
    d1.pop('location', None)
    d2 = dict(other.__dict__)
    d2.pop('location', None)
    return d1 == d2


def node_ne(self, other):
    return not self.__eq__(other)


class TestParser(TestCase):

    def setUp(self):
        self.node_patcher = patch.multiple(Node, __eq__=node_eq, __ne__=node_ne)
        self.node_patcher.start()

    def tearDown(self):
        self.node_patcher.stop()

    def parse(self, text):
        tokens = list(tokenize(text))
        try:
            return parser().parse(tokens)
        except NoParseError:
            print(tokens)
            raise

    def testImplicitTuple(self):
        self.assertEqual(
            self.parse('foo :bar 5 "baz"'),
            List([
                Tuple([Symbol('foo'),
                       Keyword('bar'), Number(5), String('baz')]),
            ]),
        )

    def testExplicitTuple(self):
        self.assertEqual(
            self.parse('foo (bar 5) "baz"'),
            List([
                Tuple([Symbol('foo'), Tuple([Symbol('bar'), Number(5)]),
                       String('baz')]),
            ]),
        )

    def testList(self):
        self.assertEqual(
            self.parse('foo [:k1 v1 1 (foo 2)]'),
            List([
                Tuple([Symbol('foo'),
                       List([Keyword('k1'),
                             Symbol('v1'),
                             Number(1),
                             Tuple([Symbol('foo'), Number(2)])])]),
            ]),
        )

    def testDict(self):
        self.assertEqual(
            self.parse('foo {:k1 v1 :k2 (v2 3)}'),
            List([
                Tuple([Symbol('foo'),
                       Dict([Keyword('k1'), Symbol('v1'),
                             Keyword('k2'), Tuple([Symbol('v2'),
                                                   Number(3)])])]),
            ]),
        )

    def testIndent(self):
        self.assertEqual(
            self.parse('foo\n'
                       '  "bar"'),
            List([
                Tuple([Symbol('foo'), String('bar')]),
            ]),
        )
        self.assertEqual(
            self.parse('foo\n'
                       '  "bar"\n'
                       '  5\n'
                       '  "baz"'),
            List([
                Tuple([Symbol('foo'),
                       Tuple([Symbol('join'),
                              String('bar'), Number(5), String('baz')])]),
            ]),
        )

    def testNestedIndent(self):
        self.assertEqual(
            self.parse('foo\n'
                       '  bar\n'
                       '    1\n'
                       '  baz\n'
                       '    2'),
            List([
                Tuple([Symbol('foo'),
                       Tuple([Symbol('join'),
                              Tuple([Symbol('bar'), Number(1)]),
                              Tuple([Symbol('baz'), Number(2)])])]),
            ]),
        )

    def testIndentedKeywords(self):
        self.assertEqual(
            self.parse('foo :k1 v1\n'
                       '  :k2 v2\n'
                       '  :k3\n'
                       '    v3'),
            List([
                Tuple([Symbol('foo'),
                       Keyword('k1'), Symbol('v1'),
                       Keyword('k2'), Symbol('v2'),
                       Keyword('k3'), Tuple([Symbol('v3')])]),
            ]),
        )
