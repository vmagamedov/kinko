from kinko.refs import NamedArgRef, RefsCollector, RecordFieldRef, ListItemRef
from kinko.refs import resolve_refs
from kinko.nodes import Symbol
from kinko.query import gen_query
from kinko.types import StringType, Record, IntType, Func, ListType, TypeVar
from kinko.checker import check, Environ

from .base import TestCase, REF_EQ_PATCHER, TYPE_EQ_PATCHER, NODE_EQ_PATCHER
from .test_parser import ParseMixin


def ctx_var(name):
    return RecordFieldRef(TypeVar[None], name)


class TestRefs(ParseMixin, TestCase):
    ctx = [NODE_EQ_PATCHER, TYPE_EQ_PATCHER, REF_EQ_PATCHER]

    def getRefs(self, src, env=None):
        node = check(self.parse(src), Environ(env))
        refs_collector = RefsCollector()
        refs_collector.visit(node)
        return node, refs_collector.refs

    def testEnv(self):
        node, refs = self.getRefs(
            """
            def foo
              span var
            """,
            {'var': StringType},
        )
        var = node.values[0].values[2].values[1]
        self.assertEqual(var, Symbol.typed(StringType, 'var'))
        self.assertEqual(var.__type__.__backref__, ctx_var('var'))

    def testGet(self):
        node, refs = self.getRefs(
            """
            def foo
              span var.attr
            """,
            {'var': Record[{'attr': StringType}]},
        )

        var_attr = node.values[0].values[2].values[1]
        var = var_attr.values[1]

        var_type = Record[{'attr': StringType}]
        self.assertEqual(var.__type__, var_type)
        self.assertEqual(var.__type__.__backref__, ctx_var('var'))

        self.assertEqual(var_attr.__type__, StringType)
        self.assertEqual(var_attr.__type__.__instance__.__backref__,
                         RecordFieldRef(var_type, 'attr'))

    def testDef(self):
        node, refs = self.getRefs(
            """
            def foo
              inc #arg.attr
            """,
            {'inc': Func[[IntType], IntType]},
        )

        arg_attr = node.values[0].values[2].values[1]
        arg = arg_attr.values[1]

        self.assertEqual(arg.__type__, Record[{'attr': IntType}])
        self.assertEqual(arg.__type__.__backref__, NamedArgRef('arg'))

        self.assertEqual(arg_attr.__type__, IntType)
        self.assertEqual(arg_attr.__type__.__instance__.__backref__,
                         RecordFieldRef(arg.__type__, 'attr'))

    def testEach(self):
        node, refs = self.getRefs(
            """
            def foo
              each r col
                inc r.attr
            """,
            {'col': ListType[Record[{'attr': IntType}]],
             'inc': Func[[IntType], IntType]},
        )
        each = node.values[0].values[2]
        each_r = each.values[1]
        each_col = each.values[2]
        r_attr = each.values[3].values[1]
        self.assertEqual(each_col.__type__.__backref__, ctx_var('col'))
        self.assertEqual(each_r.__type__.__instance__.__backref__,
                         ListItemRef(each_col.__type__.__instance__))
        self.assertEqual(r_attr.__type__.__instance__.__backref__,
                         RecordFieldRef(each_r.__type__.__instance__, 'attr'))

    def testRequirements(self):
        node = self.parse(u"""
        def baz
          div #b.count

        def bar
          span #a.name
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
        refs_collector = RefsCollector()
        refs_collector.visit(node)
        refs = resolve_refs(refs_collector.refs, 'foo')
        self.assertEqual(repr(gen_query(refs)),
                         '[{:x [:count :name]} :y]')
