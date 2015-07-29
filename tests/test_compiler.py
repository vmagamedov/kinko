import difflib
from textwrap import dedent
from unittest import TestCase

from funcparserlib.parser import NoParseError

from kinko.parser import parser
from kinko.compiler import compile_, dumps
from kinko.tokenizer import tokenize


class TestCompile(TestCase):

    def compile(self, src):
        src = dedent(src).strip() + '\n'
        tokens = list(tokenize(src))
        try:
            body = parser().parse(tokens)
        except NoParseError:
            print(tokens)
            raise
        else:
            return list(compile_(body.values[0]))

    def assertCompiles(self, src, code):
        py_ast = self.compile(src)
        first = '\n'.join(map(dumps, py_ast))
        second = dedent(code).strip()
        if first != second:
            msg = ('Compiled code is not equal:\n\n{}'
                   .format('\n'.join(difflib.ndiff(first.splitlines(),
                                                   second.splitlines()))))
            raise self.failureException(msg)

    def testTag(self):
        self.assertCompiles(
            """
            div :foo "bar" "baz"
            """,
            """
            buf.write('<div')
            buf.write(' foo="')
            buf.write('bar')
            buf.write('"')
            buf.write('>')
            buf.write('baz')
            buf.write('</div>')
            """,
        )

    def testSymbol(self):
        self.assertCompiles(
            """
            div :foo "bar" baz
            """,
            """
            buf.write('<div')
            buf.write(' foo="')
            buf.write('bar')
            buf.write('"')
            buf.write('>')
            buf.write(ctx.baz)
            buf.write('</div>')
            """,
        )

    def testJoin(self):
        self.assertCompiles(
            """
            div
              div "one"
              div "two"
            """,
            """
            buf.write('<div')
            buf.write('>')
            buf.write('<div')
            buf.write('>')
            buf.write('one')
            buf.write('</div>')
            buf.write('<div')
            buf.write('>')
            buf.write('two')
            buf.write('</div>')
            buf.write('</div>')
            """,
        )

    def testEach(self):
        self.assertCompiles(
            """
            div
              each i items
                div i
            """,
            """
            buf.write('<div')
            buf.write('>')
            for ctx.i in ctx.items:
                buf.write('<div')
                buf.write('>')
                buf.write(ctx.i)
                buf.write('</div>')
            buf.write('</div>')
            """,
        )

    def testFunc(self):
        self.assertCompiles(
            """
            foo
              each i items
                div i
            """,
            """
            buf.push()
            for ctx.i in ctx.items:
                buf.write('<div')
                buf.write('>')
                buf.write(ctx.i)
                buf.write('</div>')
            __anon1 = buf.pop()
            foo(__anon1)
            """,
        )
        self.assertCompiles(
            """
            foo
              :param
                each i items
                  div i
            """,
            """
            buf.push()
            for ctx.i in ctx.items:
                buf.write('<div')
                buf.write('>')
                buf.write(ctx.i)
                buf.write('</div>')
            __anon1 = buf.pop()
            foo(param=__anon1)
            """,
        )

    def testDef(self):
        self.assertCompiles(
            """
            def foo
              div
              each i items
                div
            """,
            """
            def foo():
                buf.write('<div')
                buf.write('>')
                buf.write('</div>')
                for ctx.i in ctx.items:
                    buf.write('<div')
                    buf.write('>')
                    buf.write('</div>')
            """,
        )
