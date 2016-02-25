# encoding: utf-8
from __future__ import unicode_literals

import difflib
from textwrap import dedent

from kinko.types import StringType, ListType, VarNamedArgs, Func, Record
from kinko.types import IntType, Union, Markup, NamedArg
from kinko.compat import _exec_in, PY3
from kinko.lookup import SimpleContext
from kinko.checker import check, Environ, NamesResolver, def_types
from kinko.checker import NamesUnResolver, collect_defs, split_defs
from kinko.out.py.compiler import compile_module, dumps

from .base import TestCase
from .test_parser import ParseMixin


class TestCompile(ParseMixin, TestCase):

    def compareSources(self, first, second):
        first = first.strip()
        if not PY3:
            first = first.replace("u'", "'")
        second = dedent(second).strip()
        if first != second:
            msg = ('Compiled code is not equal:\n\n{}'
                   .format('\n'.join(difflib.ndiff(first.splitlines(),
                                                   second.splitlines()))))
            raise self.failureException(msg)

    def assertCompiles(self, src, code, env=None):
        node = self.parse(src)
        node = check(node, Environ(env or {}))
        mod = compile_module(node)
        try:
            compile(mod, '<kinko-template>', 'exec')
        except TypeError:
            print(dumps(mod))
            raise
        else:
            self.compareSources(dumps(mod), code)

    def testTag(self):
        self.assertCompiles(
            """
            div :foo "bar" "baz"
            """,
            """
            ctx.buffer.write('<div foo="bar">baz</div>')
            """,
        )

    def testSymbol(self):
        self.assertCompiles(
            """
            div :foo "bar" baz
            """,
            """
            ctx.buffer.write('<div foo="bar">')
            ctx.buffer.write(ctx.result['baz'])
            ctx.buffer.write('</div>')
            """,
            {'baz': StringType},
        )

    def testJoin(self):
        self.assertCompiles(
            """
            div
              div "one"
              div "two"
            """,
            """
            ctx.buffer.write('<div><div>one</div><div>two</div></div>')
            """,
        )
        # self.assertCompiles(
        #     """
        #     div :class (join [1 2 3])
        #     """,
        #     """
        #     ctx.buffer.write('<div class="123"></div>')
        #     """,
        # )
        # self.assertCompiles(
        #     """
        #     div :class (join " " [1 2 3])
        #     """,
        #     """
        #     ctx.buffer.write('<div class="1 2 3"></div>')
        #     """,
        # )

    def testEach(self):
        self.assertCompiles(
            """
            div
              each i items
                div i
            """,
            """
            ctx.buffer.write('<div>')
            for i in ctx.result['items']:
                ctx.buffer.write('<div>')
                ctx.buffer.write(i)
                ctx.buffer.write('</div>')
            ctx.buffer.write('</div>')
            """,
            {'items': ListType[StringType]},
        )

    def testBuiltinFuncCall(self):
        self.assertCompiles(
            """
            a :href (url-for "foo" :bar "baz")
            """,
            """
            ctx.buffer.write('<a href="')
            ctx.buffer.write(builtins.url-for('foo', bar='baz'))
            ctx.buffer.write('"></a>')
            """,
            {'url-for': Func[[StringType, VarNamedArgs[StringType]],
                             StringType]},
        )

    def testFuncDef(self):
        self.assertCompiles(
            """
            def func
              div :class #foo
                #bar
              each i items
                div
                  #baz
            """,
            """
            def func(ctx, foo, bar, baz):
                ctx.buffer.write('<div class="')
                ctx.buffer.write(foo)
                ctx.buffer.write('">')
                ctx.buffer.write(bar)
                ctx.buffer.write('</div>')
                for i in ctx.result['items']:
                    ctx.buffer.write('<div>')
                    ctx.buffer.write(baz)
                    ctx.buffer.write('</div>')
            """,
            {'items': ListType[Record[{}]]},
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
            ctx.buffer.write('<div>')
            ctx.buffer.push()
            ctx.buffer.write('<div>')
            ctx.buffer.push()
            ctx.buffer.write('<span>Test</span>')
            baz(ctx, 3, 4, param2=ctx.buffer.pop())
            ctx.buffer.write('</div>')
            ctx.lookup('foo/bar')(ctx, 1, 2, param1=ctx.buffer.pop())
            ctx.buffer.write('</div>')
            """,
            {'foo/bar': Func[[IntType, IntType, NamedArg['param1', Markup]],
                             Markup],
             './baz': Func[[IntType, IntType, NamedArg['param2', Markup]],
                           Markup]},
        )

    def testIf(self):
        # FIXME: implement these signatures
        # self.assertCompiles(
        #     """
        #     if 1
        #       :then
        #         div "Trueish"
        #       :else
        #         div "Falseish"
        #     """,
        #     """
        #     if 1:
        #         ctx.buffer.write('<div>Trueish</div>')
        #     else:
        #         ctx.buffer.write('<div>Falseish</div>')
        #     """,
        # )
        # self.assertCompiles(
        #     """
        #     if 1
        #       :then
        #         div "Trueish"
        #     """,
        #     """
        #     if 1:
        #         ctx.buffer.write('<div>Trueish</div>')
        #     """,
        # )
        self.assertCompiles(
            """
            if 1
              div "Trueish"
            """,
            """
            if 1:
                ctx.buffer.write('<div>Trueish</div>')
            """,
        )
        self.assertCompiles(
            """
            div
              if (if 1 "true" "false")
                span "Trueish"
            """,
            """
            ctx.buffer.write('<div>')
            if ('true' if 1 else 'false'):
                ctx.buffer.write('<span>Trueish</span>')
            ctx.buffer.write('</div>')
            """,
        )
        self.assertCompiles(
            """
            div
              if (if 1 "true")
                span "Trueish"
            """,
            """
            ctx.buffer.write('<div>')
            if ('true' if 1 else None):
                ctx.buffer.write('<span>Trueish</span>')
            ctx.buffer.write('</div>')
            """,
        )

    def testGet(self):
        self.assertCompiles(
            """
            div :class foo.bar.baz
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write(ctx.result['foo']['bar']['baz'])
            ctx.buffer.write('"></div>')
            """,
            {'foo': Record[{'bar': Record[{'baz': StringType}]}]},
        )

    def testGetStmt(self):
        self.assertCompiles(
            """
            def foo
              #bar.baz
            """,
            """
            def foo(ctx, bar):
                ctx.buffer.write(bar['baz'])
            """,
        )

    def testModule(self):
        foo_node = self.parse("""
        def func1
          div
            ./func2

        def func2
          div
            bar/func3
        """)
        bar_node = self.parse("""
        def func3
          div "Text"
        """)
        foo_node = NamesResolver('foo').visit(foo_node)
        bar_node = NamesResolver('bar').visit(bar_node)

        node = collect_defs([foo_node, bar_node])
        env = Environ(def_types(node))
        node = check(node, env)

        modules = split_defs(node)

        foo_node = modules['foo']
        bar_node = modules['bar']

        foo_node = NamesUnResolver('foo').visit(foo_node)
        bar_node = NamesUnResolver('bar').visit(bar_node)

        foo_module = compile_module(foo_node)
        _exec_in(compile(foo_module, '<kinko:foo>', 'exec'), {})
        self.compareSources(
            dumps(foo_module),
            """
            def func1(ctx):
                ctx.buffer.write('<div>')
                func2(ctx)
                ctx.buffer.write('</div>')

            def func2(ctx):
                ctx.buffer.write('<div>')
                ctx.lookup('bar/func3')(ctx)
                ctx.buffer.write('</div>')
            """,
        )
        bar_module = compile_module(bar_node)
        _exec_in(compile(bar_module, '<kinko:bar>', 'exec'), {})
        self.compareSources(
            dumps(bar_module),
            """
            def func3(ctx):
                ctx.buffer.write('<div>Text</div>')
            """,
        )

    def testCompile(self):
        node = self.parse("""
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

        ctx = SimpleContext({'items': [1, 2, "Привет"]})
        ctx.buffer.push()
        ns = {}
        _exec_in(mod_code, ns)
        ns['foo'](ctx)
        content = ctx.buffer.pop()

        self.assertEqual(
            content,
            "<div><div>1</div><div>2</div><div>Привет</div></div>",
        )
