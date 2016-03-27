from kinko.query import Edge, Field, Link
from kinko.refs import ArgRef, RefsCollector, FieldRef, ItemRef, extract
from kinko.nodes import Symbol
from kinko.types import StringType, Record, IntType, Func, ListType, TypeVar
from kinko.checker import check, Environ

from .base import TestCase, REF_EQ_PATCHER, NODE_EQ_PATCHER, query_eq_patcher
from .base import STRICT_TYPE_EQ_PATCHER
from .test_parser import parse


def ctx_var(name):
    return FieldRef(None, name)


class TestRefs(TestCase):
    ctx = [NODE_EQ_PATCHER, STRICT_TYPE_EQ_PATCHER, REF_EQ_PATCHER]

    def getRefs(self, src, env=None):
        node = check(parse(src), Environ(env))
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
        var_type = TypeVar[StringType]
        var_type.__backref__ = ctx_var('var')
        self.assertEqual(var, Symbol.typed(var_type, 'var'))

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

        var_type = TypeVar[Record[{'attr': StringType}]]
        var_type.__backref__ = ctx_var('var')
        self.assertEqual(var.__type__, var_type)

        var_attr_type = TypeVar[StringType]
        var_attr_type.__backref__ = FieldRef(var_type, 'attr')
        self.assertEqual(var_attr.__type__, var_attr_type)

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
        self.assertEqual(arg.__type__,
                         TypeVar[Record[{'attr': TypeVar[IntType]}]])
        self.assertEqual(arg.__type__.__backref__, ArgRef('arg'))
        self.assertEqual(arg_attr.__type__, TypeVar[TypeVar[IntType]])
        self.assertEqual(arg_attr.__type__.__backref__,
                         FieldRef(arg.__type__, 'attr'))

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
        self.assertEqual(each_r.__type__.__backref__,
                         ItemRef(each_col.__type__))
        self.assertEqual(r_attr.__type__.__backref__,
                         FieldRef(each_r.__type__, 'attr'))

    def testRequirements(self):
        node = parse(u"""
        def baz
          div #b.count

        def bar
          span #a.name
          span y
          baz :b #a
          span #c

        def foo
          div
            each i x
              bar :a i :c 5
        """)
        node = check(node, Environ({
            'x': ListType[Record[{'name': StringType,
                                  'count': IntType}]],
            'y': StringType,
        }))
        mapping = extract(node)

        with query_eq_patcher():
            self.assertEqual(mapping['foo'],
                             Edge([Field('y'),
                                   Link('x', Edge([Field('count'),
                                                   Field('name')]))]))
