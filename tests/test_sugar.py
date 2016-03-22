from kinko.nodes import Tuple, Symbol, List, String
from kinko.sugar import translate, StringInterpolate

from .base import TestCase, NODE_EQ_PATCHER
from .test_parser import ParseMixin


class TestInterpolation(ParseMixin, TestCase):
    ctx = [NODE_EQ_PATCHER]

    def testTranslate(self):
        self.assertEqual(
            translate(String('before {a} {b.c} after')),
            Tuple([Symbol('join'), List([
                String('before '),
                Symbol('a'),
                String(' '),
                Symbol('b.c'),
                String(' after'),
            ])]),
        )
        self.assertEqual(
            translate(String('before {a-b} {b-c.d-e} after')),
            Tuple([Symbol('join'), List([
                String('before '),
                Symbol('a-b'),
                String(' '),
                Symbol('b-c.d-e'),
                String(' after'),
            ])]),
        )

    def testTranslateInvalid(self):
        self.assertEqual(
            translate(String('before {.a} {b.} {a..b} {.} {..} after')),
            String('before {.a} {b.} {a..b} {.} {..} after'),
        )
        self.assertEqual(
            translate(String('before {.a} {b.} {c} {a..b} {.} {..} after')),
            Tuple([Symbol('join'), List([
                String('before {.a} {b.} '),
                Symbol('c'),
                String(' {a..b} {.} {..} after'),
            ])]),
        )

    def testStringInterpolate(self):
        node = self.parse("""
        foo
          "bar {value} baz"
        """)
        node = StringInterpolate().visit(node)
        self.assertEqual(
            StringInterpolate().visit(node),
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
