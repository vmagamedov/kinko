# encoding: utf-8
import difflib
from textwrap import dedent
from unittest import TestCase

try:
    from unittest.mock import Mock
except ImportError:
    from mock import Mock

from kinko.refs import NamedArgRef, RecordRef, RecordFieldRef, ScalarRef
from kinko.refs import ListItemRef, ListRef, RefsCollector, resolve_refs
from kinko.query import gen_query
from kinko.utils import Buffer
from kinko.types import StringType, ListType, VarNamedArgs, Func, Record
from kinko.types import IntType, Union, Markup, NamedArg
from kinko.compat import _exec_in, PY3
from kinko.checker import check, Environ
from kinko.compiler import compile_module, dumps

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

    def testRequirements(self):
        node = self.parse(u"""
        def baz
          div #b.count

        def bar
          span (get #a name)
          span y
          baz :b #a

        def foo
          div
            each i x
              bar :a i
        """)
        node = check(node, Environ({
            'x': ListType[Record[{'name': StringType,
                                  'count': IntType}]],
            'y': StringType,
        }))

        baz = node.values[0]
        baz_getcount = baz.values[2].values[1]
        baz_getcount.__type__.__ref__ = \
            ScalarRef(RecordFieldRef(RecordRef(NamedArgRef('b')), 'count'))

        bar = node.values[1]
        bar_join = bar.values[2]
        bar_getname = bar_join.values[1].values[0].values[1]
        bar_getname.__type__.__instance__.__ref__ = \
            ScalarRef(RecordFieldRef(RecordRef(NamedArgRef('a')), 'name'))

        bar_getname_a = bar_getname.values[1]
        bar_getname_a.__type__.__ref__ = RecordRef(NamedArgRef('a'))
        bar_y = bar_join.values[1].values[1].values[1]
        bar_y.__type__.__ref__ = ScalarRef(RecordFieldRef(None, 'y'))

        bar_baz = bar_join.values[1].values[2]
        bar_baz.values[2].__type__.__ref__ = RecordRef(NamedArgRef('a'))

        foo = node.values[2]
        foo_div = foo.values[2]
        foo_each = foo_div.values[1]
        foo_i = foo_each.values[1]
        foo_i.__type__.__ref__ = \
            RecordRef(ListItemRef(ListRef(RecordFieldRef(None, 'x'))))
        foo_x = foo_each.values[2]
        foo_x.__type__.__ref__ = ListRef(RecordFieldRef(None, 'x'))

        foo_v = RefsCollector()
        foo_v.visit(foo)
        print(foo_v.refs)

        bar_v = RefsCollector()
        bar_v.visit(bar)
        print(bar_v.refs)

        baz_v = RefsCollector()
        baz_v.visit(baz)
        print(baz_v.refs)

        all_refs = {'foo': foo_v.refs, 'bar': bar_v.refs, 'baz': baz_v.refs}
        refs = resolve_refs(all_refs, 'foo')
        print(refs)

        print(gen_query(refs))

        # 1/0
