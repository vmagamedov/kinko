from kinko.nodes import Tuple, Symbol, List, String
from kinko.sugar import InterpolateString

from .base import TestCase, NODE_EQ_PATCHER
from .test_parser import parse, parse_raw


class TestInterpolateString(TestCase):
    ctx = [NODE_EQ_PATCHER]

    def interpolate(self, node):
        return InterpolateString().visit(node)

    def checkLocation(self, src, node, fragment):
        a, b = node.location.start.offset, node.location.end.offset
        assert src[a:b] == fragment

    def testInterpolate(self):
        src = 'foo "before {a} {b.c} after"'
        node = self.interpolate(parse_raw(src))
        self.assertEqual(
            node,
            List([Tuple([
                Symbol('foo'),
                Tuple([Symbol('join'), List([
                    String('before '),
                    Symbol('a'),
                    String(' '),
                    Symbol('b.c'),
                    String(' after'),
                ])]),
            ])]),
        )
        items = node.values[0].values[1].values[1].values
        self.checkLocation(src, items[0], '"before ')
        self.checkLocation(src, items[1], 'a')
        self.checkLocation(src, items[2], ' ')
        self.checkLocation(src, items[3], 'b.c')
        self.checkLocation(src, items[4], ' after"')

    def testInterpolateFirst(self):
        src = 'foo "{a} after"'
        node = self.interpolate(parse_raw(src))
        self.assertEqual(
            node,
            List([Tuple([
                Symbol('foo'),
                Tuple([Symbol('join'), List([
                    Symbol('a'),
                    String(' after'),
                ])]),
            ])]),
        )
        items = node.values[0].values[1].values[1].values
        self.checkLocation(src, items[0], 'a')
        self.checkLocation(src, items[1], ' after"')

    def testInterpolateLast(self):
        src = 'foo "before {a}"'
        node = self.interpolate(parse_raw(src))
        self.assertEqual(
            node,
            List([Tuple([
                Symbol('foo'),
                Tuple([Symbol('join'), List([
                    String('before '),
                    Symbol('a'),
                ])]),
            ])]),
        )
        items = node.values[0].values[1].values[1].values
        self.checkLocation(src, items[0], '"before ')
        self.checkLocation(src, items[1], 'a')

    def testInterpolateVarOnly(self):
        src = 'foo "{a}"'
        node = self.interpolate(parse_raw(src))
        self.assertEqual(
            node,
            List([Tuple([
                Symbol('foo'),
                Symbol('a'),
            ])]),
        )
        self.checkLocation(src, node.values[0].values[1], 'a')

    def testInterpolateStringOnly(self):
        src = 'foo "text"'
        node = self.interpolate(parse_raw(src))
        self.assertEqual(
            node,
            List([Tuple([
                Symbol('foo'),
                String('text'),
            ])]),
        )
        self.checkLocation(src, node.values[0].values[1], '"text"')

    def testInterpolateEmptyString(self):
        src = 'foo ""'
        node = self.interpolate(parse_raw(src))
        self.assertEqual(
            node,
            List([Tuple([
                Symbol('foo'),
                String(''),
            ])]),
        )
        self.checkLocation(src, node.values[0].values[1], '""')

    def testInterpolateInvalid(self):
        self.assertEqual(
            self.interpolate(parse_raw('foo "before {.a} {b.} {a..b} {.} '
                                       '{..} after"')),
            List([Tuple([
                Symbol('foo'),
                String('before {.a} {b.} {a..b} {.} {..} after'),
            ])]),
        )
        self.assertEqual(
            self.interpolate(parse_raw('foo "before {.a} {b.} {c} {a..b} '
                                       '{.} {..} after"')),
            List([Tuple([
                Symbol('foo'),
                Tuple([Symbol('join'), List([
                    String('before {.a} {b.} '),
                    Symbol('c'),
                    String(' {a..b} {.} {..} after'),
                ])]),
            ])]),
        )

    def testParser(self):
        node = parse("""
        foo
          "bar {value} baz"
        """)
        self.assertEqual(
            node,
            List([
                Tuple([
                    Symbol('foo'),
                    Tuple([Symbol('join'), List([
                        String('bar '),
                        Symbol('value'),
                        String(' baz'),
                    ])]),
                ]),
            ]),
        )
