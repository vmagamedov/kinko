from kinko.nodes import Tuple, Symbol, List, String
from kinko.sugar import InterpolateString

from .base import TestCase, NODE_EQ_PATCHER
from .test_parser import ParseMixin


class TestInterpolateString(ParseMixin, TestCase):
    ctx = [NODE_EQ_PATCHER]

    def interpolate(self, node):
        return InterpolateString().visit(node)

    def testInterpolate(self):
        self.assertEqual(
            self.interpolate(String('before {a} {b.c} after')),
            Tuple([Symbol('join'), List([
                String('before '),
                Symbol('a'),
                String(' '),
                Symbol('b.c'),
                String(' after'),
            ])]),
        )
        self.assertEqual(
            self.interpolate(String('before {a-b} {b-c.d-e} after')),
            Tuple([Symbol('join'), List([
                String('before '),
                Symbol('a-b'),
                String(' '),
                Symbol('b-c.d-e'),
                String(' after'),
            ])]),
        )

    def testInterpolateInvalid(self):
        self.assertEqual(
            self.interpolate(String('before {.a} {b.} {a..b} {.} {..} after')),
            String('before {.a} {b.} {a..b} {.} {..} after'),
        )
        self.assertEqual(
            self.interpolate(String('before {.a} {b.} {c} {a..b} {.} {..} '
                                    'after')),
            Tuple([Symbol('join'), List([
                String('before {.a} {b.} '),
                Symbol('c'),
                String(' {a..b} {.} {..} after'),
            ])]),
        )

    def testParser(self):
        node = self.parse("""
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
