# encoding: utf-8
from __future__ import unicode_literals

import difflib
from textwrap import dedent

from kinko.types import StringType, ListType, VarNamedArgs, Func, Record, Option
from kinko.types import IntType, Union, Markup, NamedArg, BoolType
from kinko.compat import _exec_in, PY3, text_type_name
from kinko.lookup import SimpleContext
from kinko.checker import check, Environ, NamesResolver, def_types
from kinko.checker import NamesUnResolver, collect_defs, split_defs
from kinko.compile.python import compile_module, dumps

from .base import TestCase
from .test_parser import parse


class TestCompiler(TestCase):

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
        node = parse(src)
        node = check(node, Environ(env))
        mod = compile_module(node)
        try:
            compile(mod, '<kinko-template>', 'exec')
        except TypeError:
            print(dumps(mod))
            raise
        else:
            self.compareSources(dumps(mod), code)

    def assertRenders(self, src, content, context=None, env=None):
        node = parse(src)
        node = check(node, Environ(env))
        mod = compile_module(node)
        mod_code = compile(mod, '<kinko-template>', 'exec')

        ctx = SimpleContext(context or {})
        ctx.buffer.push()
        ns = {}
        _exec_in(mod_code, ns)
        ns['foo'](ctx)
        rendered = ctx.buffer.pop()

        self.assertEqual(rendered, content)

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
            ctx.buffer.write_unsafe(ctx.result['baz'])
            ctx.buffer.write('</div>')
            """,
            {'baz': StringType},
        )

    def testJoinMarkup(self):
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

    def testJoinStr(self):
        self.assertCompiles(
            """
            div :class (join "SEP" [1 2 3])
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write_unsafe('SEP'.join(({}(_i) for _i in [1, 2, 3])))
            ctx.buffer.write('"></div>')
            """.format(text_type_name),
        )

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
                ctx.buffer.write_unsafe(i)
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
            ctx.buffer.write_unsafe(ctx.builtins['url-for']('foo', bar='baz'))
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
                ctx.buffer.write_optional_unsafe(foo)
                ctx.buffer.write('">')
                ctx.buffer.write_optional_unsafe(bar)
                ctx.buffer.write('</div>')
                for i in ctx.result['items']:
                    ctx.buffer.write('<div>')
                    ctx.buffer.write_optional_unsafe(baz)
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

    def testLetStatement(self):
        self.assertCompiles(
            """
            let [x 1 y 2]
              h1
            """,
            """
            x = 1
            y = 2
            ctx.buffer.write('<h1></h1>')
            """,
        )

    def testLetExpression(self):
        expr = "[ctx.builtins['add'](x, y) for (x, y) in [(1, 2)]][0]"
        self.assertCompiles(
            """
            div :class (let [x 1 y 2] (add x y))
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write({})
            ctx.buffer.write('"></div>')
            """.format(expr),
            {'add': Func[[IntType, IntType], IntType]},
        )

    def testIfThenStatement(self):
        self.assertCompiles(
            """
            if 1 (h1)
            """,
            """
            if 1:
                ctx.buffer.write('<h1></h1>')
            """,
        )

    def testIfThenExpression(self):
        self.assertCompiles(
            """
            div :class (if 1 "a")
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write_optional_unsafe(('a' if 1 else None))
            ctx.buffer.write('"></div>')
            """,
        )

    def testIfThenElseStatement(self):
        self.assertCompiles(
            """
            if 1 (h1) (h2)
            """,
            """
            if 1:
                ctx.buffer.write('<h1></h1>')
            else:
                ctx.buffer.write('<h2></h2>')
            """,
        )

    def testIfThenElseExpression(self):
        self.assertCompiles(
            """
            div :class (if 1 "a" "b")
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write_unsafe(('a' if 1 else 'b'))
            ctx.buffer.write('"></div>')
            """,
        )

    def testIfNamedThenElseStatement(self):
        self.assertCompiles(
            """
            if 1 :then (h1) :else (h2)
            """,
            """
            if 1:
                ctx.buffer.write('<h1></h1>')
            else:
                ctx.buffer.write('<h2></h2>')
            """,
        )

    def testIfNamedThenElseExpression(self):
        self.assertCompiles(
            """
            div :class (if 1 :then "a" :else "b")
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write_unsafe(('a' if 1 else 'b'))
            ctx.buffer.write('"></div>')
            """,
        )

    def testIfSomeStatement(self):
        self.assertCompiles(
            """
            if-some [x foo.bar]
              h1 (inc x)
            """,
            """
            x = ctx.result['foo']['bar']
            if (x is not None):
                ctx.buffer.write('<h1>')
                ctx.buffer.write(ctx.builtins['inc'](x))
                ctx.buffer.write('</h1>')
            """,
            {'foo': Record[{'bar': Option[IntType]}],
             'inc': Func[[IntType], IntType]},
        )

    def testIfSomeExpression(self):
        expr = ("[(ctx.builtins['inc'](x) if (x is not None) else None) "
                "for (x,) in [(ctx.result['foo']['bar'],)]][0]")
        self.assertCompiles(
            """
            div :class (if-some [x foo.bar] (inc x))
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write_optional({})
            ctx.buffer.write('"></div>')
            """.format(expr),
            {'foo': Record[{'bar': Option[IntType]}],
             'inc': Func[[IntType], IntType]},
        )

    def testIfSomeElseStatement(self):
        self.assertCompiles(
            """
            if-some [x foo.bar] (h1 x) (h2 x)
            """,
            """
            x = ctx.result['foo']['bar']
            if (x is not None):
                ctx.buffer.write('<h1>')
                ctx.buffer.write(x)
                ctx.buffer.write('</h1>')
            else:
                ctx.buffer.write('<h2>')
                ctx.buffer.write(x)
                ctx.buffer.write('</h2>')
            """,
            {'foo': Record[{'bar': Option[IntType]}]},
        )

    def testIfSomeElseExpression(self):
        expr = ("[(ctx.builtins['inc'](x) if (x is not None) "
                "else ctx.builtins['dec'](x)) "
                "for (x,) in [(ctx.result['foo']['bar'],)]][0]")
        self.assertCompiles(
            """
            div :class (if-some [x foo.bar] (inc x) (dec x))
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write({})
            ctx.buffer.write('"></div>')
            """.format(expr),
            {'foo': Record[{'bar': Option[IntType]}],
             'inc': Func[[IntType], IntType],
             'dec': Func[[IntType], IntType]},
        )

    def testIfSomeNamedElseStatement(self):
        self.assertCompiles(
            """
            if-some [x foo.bar] :then (h1 x) :else (h2 x)
            """,
            """
            x = ctx.result['foo']['bar']
            if (x is not None):
                ctx.buffer.write('<h1>')
                ctx.buffer.write(x)
                ctx.buffer.write('</h1>')
            else:
                ctx.buffer.write('<h2>')
                ctx.buffer.write(x)
                ctx.buffer.write('</h2>')
            """,
            {'foo': Record[{'bar': Option[IntType]}]},
        )

    def testIfSomeNamedElseExpression(self):
        expr = ("[(ctx.builtins['inc'](x) if (x is not None) "
                "else ctx.builtins['dec'](x)) "
                "for (x,) in [(ctx.result['foo']['bar'],)]][0]")
        self.assertCompiles(
            """
            div :class (if-some [x foo.bar] :then (inc x) :else (dec x))
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write({})
            ctx.buffer.write('"></div>')
            """.format(expr),
            {'foo': Record[{'bar': Option[IntType]}],
             'inc': Func[[IntType], IntType],
             'dec': Func[[IntType], IntType]},
        )

    def testGet(self):
        self.assertCompiles(
            """
            div :class foo.bar.baz
            """,
            """
            ctx.buffer.write('<div class="')
            ctx.buffer.write_unsafe(ctx.result['foo']['bar']['baz'])
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
        foo_node = parse("""
        def func1
          div
            ./func2

        def func2
          div
            bar/func3
        """)
        bar_node = parse("""
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
        self.assertRenders(
            """
            def foo
              div
                each i items
                  div i
            """,
            """<div><div>1</div><div>2</div><div>Привет</div></div>""",
            {
                'items': [1, 2, "Привет"],
            },
            {
                'items': ListType[Union[StringType, IntType]],
            },
        )

    def testCompileNone(self):
        self.assertRenders(
            """
            def foo
              div
                if bar "true"
            """,
            """<div></div>""",
            {
                'bar': False,
            },
            {
                'bar': BoolType,
            },
        )
