import difflib
from textwrap import dedent

from kinko.nodes import Tuple, Symbol, Keyword, String, List, Placeholder
from kinko.printer import Printer

from .base import TestCase


class TestPrinter(TestCase):

    def assertPrints(self, node, output):
        first = Printer.dumps(node)
        second = dedent(output).strip() + '\n'
        if first != second:
            msg = ('Printed code is not equal:\n\n{}'
                   .format('\n'.join(difflib.ndiff(first.splitlines(),
                                                   second.splitlines()))))
            raise self.failureException(msg)

    def testSimple(self):
        self.assertPrints(
            Tuple([Symbol('html'),
                   Keyword('foo'), String('bar'), Symbol('baz')]),
            """
            html :foo "bar" baz
            """,
        )

    def testNested(self):
        self.assertPrints(
            Tuple([Symbol('html'),
                   Keyword('foo'), String('bar'),
                   Tuple([Symbol('head')])]),
            """
            html :foo "bar"
              head
            """,
        )

    def testJoin(self):
        self.assertPrints(
            Tuple([Symbol('html'),
                   Keyword('foo'), String('bar'),
                   Tuple([Symbol('join'), List([
                       Tuple([Symbol('head')]),
                       Tuple([Symbol('body')]),
                   ])])]),
            """
            html :foo "bar"
              head
              body
            """,
        )

    def testGet(self):
        self.assertPrints(
            Tuple([Symbol('html'),
                   Keyword('foo'), Tuple([Symbol('get'), Symbol('bar'),
                                          Symbol('baz')])]),
            """
            html :foo bar.baz
            """,
        )
        self.assertPrints(
            Tuple([Symbol('html'),
                   Keyword('foo'), Tuple([Symbol('get'), Placeholder('bar'),
                                          Symbol('baz')])]),
            """
            html :foo #bar.baz
            """,
        )
