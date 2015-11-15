# encoding: utf-8
import difflib
from textwrap import dedent

from kinko.utils import Buffer
from kinko.types import StringType, ListType, VarNamedArgs, Func, Record
from kinko.types import IntType, Union, Markup, NamedArg
from kinko.compat import _exec_in, PY3
from kinko.checker import check, Environ
from kinko.compiler import compile_module, dumps

from .base import TestCase, Mock
from .test_parser import ParseMixin


class TestCompile(ParseMixin, TestCase):

    def assertCompiles(self, src, code, env=None):
        node = self.parse(src)
        node = check(node, Environ(env or {}))
        mod = compile_module(node)
        first = dumps(mod)
        if not PY3:
            first = first.replace("u'", "'")
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
            u"""
            div :foo "bar" "baz"
            """,
            u"""
            buf.write('<div foo="bar">baz</div>')
            """,
        )

    def testSymbol(self):
        self.assertCompiles(
            u"""
            div :foo "bar" baz
            """,
            u"""
            buf.write('<div foo="bar">')
            buf.write(ctx.baz)
            buf.write('</div>')
            """,
            {'baz': StringType},
        )

    def testJoin(self):
        self.assertCompiles(
            u"""
            div
              div "one"
              div "two"
            """,
            u"""
            buf.write('<div><div>one</div><div>two</div></div>')
            """,
        )
        # self.assertCompiles(
        #     u"""
        #     div :class (join [1 2 3])
        #     """,
        #     u"""
        #     buf.write('<div class="123"></div>')
        #     """,
        # )
        # self.assertCompiles(
        #     u"""
        #     div :class (join " " [1 2 3])
        #     """,
        #     u"""
        #     buf.write('<div class="1 2 3"></div>')
        #     """,
        # )

    def testEach(self):
        self.assertCompiles(
            u"""
            div
              each i items
                div i
            """,
            u"""
            buf.write('<div>')
            for ctx.i in ctx.items:
                buf.write('<div>')
                buf.write(ctx.i)
                buf.write('</div>')
            buf.write('</div>')
            """,
            {'items': ListType[StringType]},
        )

    def testBuiltinFuncCall(self):
        self.assertCompiles(
            u"""
            a :href (url-for "foo" :bar "baz")
            """,
            u"""
            buf.write('<a href="')
            buf.write(builtins.url-for('foo', bar='baz'))
            buf.write('"></a>')
            """,
            {'url-for': Func[[StringType, VarNamedArgs[StringType]],
                             StringType]},
        )

    def testFuncDef(self):
        self.assertCompiles(
            u"""
            def foo
              div
                #bar
              each i items
                div
                  #baz
            """,
            u"""
            def foo(bar, baz):
                buf.write('<div>')
                buf.write(bar)
                buf.write('</div>')
                for ctx.i in ctx.items:
                    buf.write('<div>')
                    buf.write(baz)
                    buf.write('</div>')
            """,
            {'items': ListType[Record[{}]]},
        )

    def testFuncCall(self):
        self.assertCompiles(
            u"""
            div
              foo/bar 1 2
                :param1
                  div
                    ./baz 3 4
                      :param2
                        span "Test"
            """,
            u"""
            buf.write('<div>')
            buf.push()
            buf.write('<div>')
            buf.push()
            buf.write('<span>Test</span>')
            baz(3, 4, param2=buf.pop())
            buf.write('</div>')
            foo.bar(1, 2, param1=buf.pop())
            buf.write('</div>')
            """,
            {'foo/bar': Func[[IntType, IntType, NamedArg['param1', Markup]],
                             Markup],
             './baz': Func[[IntType, IntType, NamedArg['param2', Markup]],
                           Markup]},
        )

    def testIf(self):
        # FIXME: implement these signatures
        # self.assertCompiles(
        #     u"""
        #     if 1
        #       :then
        #         div "Trueish"
        #       :else
        #         div "Falseish"
        #     """,
        #     u"""
        #     if 1:
        #         buf.write('<div>Trueish</div>')
        #     else:
        #         buf.write('<div>Falseish</div>')
        #     """,
        # )
        # self.assertCompiles(
        #     u"""
        #     if 1
        #       :then
        #         div "Trueish"
        #     """,
        #     u"""
        #     if 1:
        #         buf.write('<div>Trueish</div>')
        #     """,
        # )
        self.assertCompiles(
            u"""
            if 1
              div "Trueish"
            """,
            u"""
            if 1:
                buf.write('<div>Trueish</div>')
            """,
        )
        self.assertCompiles(
            u"""
            div
              if (if 1 "true" "false")
                span "Trueish"
            """,
            u"""
            buf.write('<div>')
            if ('true' if 1 else 'false'):
                buf.write('<span>Trueish</span>')
            buf.write('</div>')
            """,
        )
        self.assertCompiles(
            u"""
            div
              if (if 1 "true")
                span "Trueish"
            """,
            u"""
            buf.write('<div>')
            if ('true' if 1 else None):
                buf.write('<span>Trueish</span>')
            buf.write('</div>')
            """,
        )

    def testGet(self):
        self.assertCompiles(
            u"""
            div :class foo.bar.baz
            """,
            u"""
            buf.write('<div class="')
            buf.write(ctx.foo.bar.baz)
            buf.write('"></div>')
            """,
            {'foo': Record[{'bar': Record[{'baz': StringType}]}]},
        )

    def testCompile(self):
        node = self.parse(u"""
        def foo
          div
            each i items
              div i
        """)
        node = check(node, Environ({
            'items': ListType[Union[StringType, IntType]],
        }))
        mod = compile_module(node)
        mod_code = compile(mod, '<kinko-template>', 'exec')

        ctx = Mock()
        ctx.items = [1, 2, u"Привет"]

        buf = Buffer()
        buf.push()
        ns = {'buf': buf, 'ctx': ctx}
        _exec_in(mod_code, ns)
        ns['foo']()
        content = buf.pop()

        self.assertEqual(
            content,
            u"<div><div>1</div><div>2</div><div>Привет</div></div>",
        )
