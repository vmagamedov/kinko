from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from funcparserlib.parser import NoParseError

from kinko.nodes import Node, Symbol, Tuple, String, Number, Keyword, Dict, List
from kinko.nodes import Placeholder
from kinko.parser import parser

from .test_tokenizer import TokenizeMixin


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


class ParseMixin(TokenizeMixin):

    def parse(self, src):
        tokens = list(self.tokenize(src))
        try:
            return parser().parse(tokens)
        except NoParseError:
            print(tokens)
            raise


class TestParser(ParseMixin, TestCase):

    def setUp(self):
        self.node_patcher = patch.multiple(Node, __eq__=node_eq, __ne__=node_ne)
        self.node_patcher.start()

    def tearDown(self):
        self.node_patcher.stop()

    def assertParse(self, src, node):
        return self.assertEqual(self.parse(src), node)

    def testSymbol(self):
        self.assertParse(
            'print foo foo.bar foo.bar.baz',
            List([
                Tuple([Symbol('print'),
                       Symbol('foo'),
                       Tuple([Symbol('get'),
                              Symbol('foo'), Symbol('bar')]),
                       Tuple([Symbol('get'),
                              Tuple([Symbol('get'),
                                     Symbol('foo'), Symbol('bar')]),
                              Symbol('baz')])]),
            ]),
        )

    def testPlaceholder(self):
        self.assertParse(
            'print #foo #foo.bar #foo.bar.baz',
            List([
                Tuple([Symbol('print'),
                       Placeholder('foo'),
                       Tuple([Symbol('get'),
                              Placeholder('foo'), Symbol('bar')]),
                       Tuple([Symbol('get'),
                              Tuple([Symbol('get'),
                                     Placeholder('foo'), Symbol('bar')]),
                              Symbol('baz')])]),
            ]),
        )

    def testImplicitTuple(self):
        self.assertParse(
            'foo :bar 5 "baz"',
            List([
                Tuple([Symbol('foo'),
                       Keyword('bar'), Number(5), String('baz')]),
            ]),
        )

    def testExplicitTuple(self):
        self.assertParse(
            'foo (bar 5) "baz"',
            List([
                Tuple([Symbol('foo'), Tuple([Symbol('bar'), Number(5)]),
                       String('baz')]),
            ]),
        )

    def testList(self):
        self.assertParse(
            'foo [:k1 v1 1 (foo 2)]',
            List([
                Tuple([Symbol('foo'),
                       List([Keyword('k1'),
                             Symbol('v1'),
                             Number(1),
                             Tuple([Symbol('foo'), Number(2)])])]),
            ]),
        )

    def testDict(self):
        self.assertParse(
            'foo {:k1 v1 :k2 (v2 3)}',
            List([
                Tuple([Symbol('foo'),
                       Dict([Keyword('k1'), Symbol('v1'),
                             Keyword('k2'), Tuple([Symbol('v2'),
                                                   Number(3)])])]),
            ]),
        )

    def testIndent(self):
        self.assertParse(
            """
            foo
              "bar"
            """,
            List([
                Tuple([Symbol('foo'), String('bar')]),
            ]),
        )
        self.assertParse(
            """
            foo
              "bar"
              5
              "baz"
            """,
            List([
                Tuple([Symbol('foo'),
                       Tuple([Symbol('join'),
                              List([String('bar'), Number(5),
                                    String('baz')])])]),
            ]),
        )

    def testNestedIndent(self):
        self.assertParse(
            """
            foo
              bar
                1
              baz
                2
            """,
            List([
                Tuple([Symbol('foo'),
                       Tuple([Symbol('join'),
                              List([Tuple([Symbol('bar'), Number(1)]),
                                    Tuple([Symbol('baz'), Number(2)])])])]),
            ]),
        )

    def testIndentedKeywords(self):
        self.assertParse(
            """
            foo :k1 v1
              :k2 v2
              :k3
                v3
            """,
            List([
                Tuple([Symbol('foo'),
                       Keyword('k1'), Symbol('v1'),
                       Keyword('k2'), Symbol('v2'),
                       Keyword('k3'), Tuple([Symbol('v3')])]),
            ]),
        )

    def testMixedIndentedArguments(self):
        self.assertParse(
            """
            foo :k1 v1
              :k2 v2
              :k3
                v3
              v4
              v5
            """,
            List([
                Tuple([Symbol('foo'),
                       Keyword('k1'), Symbol('v1'),
                       Keyword('k2'), Symbol('v2'),
                       Keyword('k3'), Tuple([Symbol('v3')]),
                       Tuple([Symbol('join'),
                              List([Tuple([Symbol('v4')]),
                                    Tuple([Symbol('v5')])])])]),
            ]),
        )
