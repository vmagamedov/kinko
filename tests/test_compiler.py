import difflib
from textwrap import dedent
from unittest import TestCase

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from kinko.compat import _exec_in
from kinko.compiler import compile_module, dumps

from .test_parser import ParseMixin


class TestCompile(ParseMixin, TestCase):

    def assertCompiles(self, src, code):
        mod = compile_module(self.parse(src))
        first = dumps(mod)
        try:
            compile(mod, '<kinko-template>', 'exec')
        except TypeError:
            print(first)
            raise
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
        self.assertCompiles(
            """
            div :class (join [1 2 3])
            """,
            """
            buf.write('<div')
            buf.write(' class="')
            buf.write(1)
            buf.write(2)
            buf.write(3)
            buf.write('"')
            buf.write('>')
            buf.write('</div>')
            """,
        )
        self.assertCompiles(
            """
            div :class (join " " [1 2 3])
            """,
            """
            buf.write('<div')
            buf.write(' class="')
            buf.write(1)
            buf.write(' ')
            buf.write(2)
            buf.write(' ')
            buf.write(3)
            buf.write('"')
            buf.write('>')
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

    def testBuiltinFuncCall(self):
        self.assertCompiles(
            """
            a :href (url-for "foo" :bar "baz")
            """,
            """
            buf.write('<a')
            buf.write(' href="')
            buf.write(builtins.url-for('foo', bar='baz'))
            buf.write('"')
            buf.write('>')
            buf.write('</a>')
            """,
        )

    def testFuncDef(self):
        self.assertCompiles(
            """
            def foo
              div
                #bar
              each i items
                div
                  #baz
            """,
            """
            def foo(bar, baz):
                buf.write('<div')
                buf.write('>')
                buf.write(bar)
                buf.write('</div>')
                for ctx.i in ctx.items:
                    buf.write('<div')
                    buf.write('>')
                    buf.write(baz)
                    buf.write('</div>')
            """,
        )

    def testFuncCall(self):
        self.assertCompiles(
            """
            div
              foo/bar 1 2
                :param1
                  div
                    ./baz 3 4
                      :param2
                        span "Test"
            """,
            """
            buf.write('<div')
            buf.write('>')
            buf.push()
            buf.write('<div')
            buf.write('>')
            buf.push()
            buf.write('<span')
            buf.write('>')
            buf.write('Test')
            buf.write('</span>')
            baz(3, 4, param2=buf.pop())
            buf.write('</div>')
            foo.bar(1, 2, param1=buf.pop())
            buf.write('</div>')
            """,
        )

    def testIf(self):
        self.assertCompiles(
            """
            if 1
              :then
                div "Trueish"
              :else
                div "Falseish"
            """,
            """
            if 1:
                buf.write('<div')
                buf.write('>')
                buf.write('Trueish')
                buf.write('</div>')
            else:
                buf.write('<div')
                buf.write('>')
                buf.write('Falseish')
                buf.write('</div>')
            """,
        )
        self.assertCompiles(
            """
            if 1
              :then
                div "Trueish"
            """,
            """
            if 1:
                buf.write('<div')
                buf.write('>')
                buf.write('Trueish')
                buf.write('</div>')
            """,
        )
        self.assertCompiles(
            """
            if 1
              div "Trueish"
            """,
            """
            if 1:
                buf.write('<div')
                buf.write('>')
                buf.write('Trueish')
                buf.write('</div>')
            """,
        )
        self.assertCompiles(
            """
            div
              if (if 1 "true" "false")
                "Trueish"
            """,
            """
            buf.write('<div')
            buf.write('>')
            if ('true' if 1 else 'false'):
                buf.write('Trueish')
            buf.write('</div>')
            """,
        )
        self.assertCompiles(
            """
            div
              if (if 1 "true")
                "Trueish"
            """,
            """
            buf.write('<div')
            buf.write('>')
            if ('true' if 1 else None):
                buf.write('Trueish')
            buf.write('</div>')
            """,
        )

    def testGet(self):
        self.assertCompiles(
            """
            div :class foo.bar.baz
            """,
            """
            buf.write('<div')
            buf.write(' class="')
            buf.write(ctx.foo.bar.baz)
            buf.write('"')
            buf.write('>')
            buf.write('</div>')
            """,
        )

    def testCompile(self):
        mod = compile_module(self.parse("""
        def foo
          div
            each i items
              div i
        """))
        mod_code = compile(mod, '<kinko-template>', 'exec')

        output = []

        buf = Mock()
        buf.write = lambda s: output.append(s)

        ctx = Mock()
        ctx.items = [1, 2, 3]

        ns = {'buf': buf, 'ctx': ctx}
        _exec_in(mod_code, ns)

        ns['foo']()
        self.assertEqual(output, [
            '<div', '>',
            '<div', '>', 1, '</div>',
            '<div', '>', 2, '</div>',
            '<div', '>', 3, '</div>',
            '</div>',
        ])
