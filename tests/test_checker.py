from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from kinko.nodes import Tuple, Symbol, Number, Node, Keyword, List, Placeholder
from kinko.nodes import String
from kinko.types import Func, IntType, StringType, NamedArg, TypeVar, GenericMeta
from kinko.types import RecordType, ListType, Union, DictType, Option
from kinko.checker import check, split_args, unsplit_args, KinkoTypeError, unify
from kinko.checker import BUILTINS

from .test_parser import node_eq, node_ne, ParseMixin


def type_eq(self, other):
    if type(self) is not type(other):
        return False
    d1 = dict(self.__dict__)
    d1.pop('__dict__')
    d1.pop('__weakref__')
    d2 = dict(other.__dict__)
    d2.pop('__dict__')
    d2.pop('__weakref__')
    return d1 == d2


def type_ne(self, other):
    return not self.__eq__(other)


LET_TYPE = BUILTINS['let']
DEF_TYPE = BUILTINS['def']
GET_TYPE = BUILTINS['get']
IF_TYPE = BUILTINS['if']
EACH_TYPE = BUILTINS['each']
IF_SOME_TYPE = BUILTINS['if-some']


class TestChecker(ParseMixin, TestCase):

    def parse_expr(self, src):
        return self.parse(src).values[0]

    def setUp(self):
        self.node_patcher = patch.multiple(Node, __eq__=node_eq, __ne__=node_ne)
        self.node_patcher.start()
        self.type_patcher = patch.multiple(GenericMeta,
                                           __eq__=type_eq, __ne__=type_ne)
        self.type_patcher.start()

    def tearDown(self):
        self.type_patcher.stop()
        self.node_patcher.stop()

    def check(self, src, env=None):
        return check(self.parse_expr(src), env or {})

    def assertChecks(self, src, typed, extra_env=None):
        self.assertEqual(self.check(src, extra_env), typed)

    def testSplitArgs(self):
        self.assertEqual(
            split_args([Number(1), Number(2), Keyword('foo'), Number(3)]),
            ([Number(1), Number(2)], {'foo': Number(3)}),
        )
        self.assertEqual(
            split_args([Keyword('foo'), Number(1), Number(2), Number(3)]),
            ([Number(2), Number(3)], {'foo': Number(1)}),
        )
        self.assertEqual(
            unsplit_args([Number(1), Number(2)], {'foo': Number(3)}),
            [Number(1), Number(2), Keyword('foo'), Number(3)],
        )
        with self.assertRaises(TypeError):
            split_args([Number(1), Keyword('foo')])

    def testUnifyType(self):
        unify(IntType, IntType)

        with self.assertRaises(KinkoTypeError):
            unify(IntType, StringType)

    def testUnifyTypeVar(self):
        a = TypeVar[None]
        unify(a, IntType)
        self.assertEqual(a.__instance__, IntType)

        b = TypeVar[None]
        unify(IntType, b)
        self.assertEqual(b.__instance__, IntType)

        with self.assertRaises(KinkoTypeError):
            unify(TypeVar[IntType], StringType)

    def testUnifyUnion(self):
        a = Union[StringType, IntType]
        unify(a, a)
        with self.assertRaises(KinkoTypeError):
            unify(a, StringType)
        unify(IntType, a)
        unify(StringType, a)

    def testUnifyRecordType(self):
        rec_type = RecordType[{'a': IntType}]
        unify(rec_type, RecordType[{'b': IntType}])
        self.assertEqual(rec_type, RecordType[{'a': IntType, 'b': IntType}])

        with self.assertRaises(KinkoTypeError):
            unify(RecordType[{'a': IntType}], RecordType[{'a': StringType}])

    def testUnifyListType(self):
        list_type = ListType[TypeVar[None]]
        unify(list_type, ListType[IntType])
        self.assertEqual(list_type.__item_type__.__instance__, IntType)

    def testUnifyDictType(self):
        dict_type = DictType[TypeVar[None], TypeVar[None]]
        unify(dict_type, DictType[StringType, IntType])
        self.assertEqual(dict_type.__key_type__.__instance__, StringType)
        self.assertEqual(dict_type.__value_type__.__instance__, IntType)

    def testFunc(self):
        inc_type = Func[[IntType], IntType]
        self.assertChecks(
            'inc 1',
            Tuple.typed(IntType, [Symbol.typed(inc_type, 'inc'),
                                  Number.typed(IntType, 1)]),
            {'inc': inc_type},
        )

        inc_step_type = Func[[IntType, NamedArg['step', IntType]], IntType]
        self.assertChecks(
            'inc-step 1 :step 2',
            Tuple.typed(IntType, [Symbol.typed(inc_step_type, 'inc-step'),
                                  Number.typed(IntType, 1),
                                  Keyword('step'), Number.typed(IntType, 2)]),
            {'inc-step': inc_step_type},
        )
        with self.assertRaises(KinkoTypeError):
            self.check('inc "foo"', {'inc': inc_type})

    def testEnvVar(self):
        inc_type = Func[[IntType], IntType]
        self.assertChecks(
            """
            inc var
            """,
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Symbol.typed(IntType, 'var'),
            ]),
            {'inc': inc_type, 'var': IntType},
        )

    def testLet(self):
        inc_type = Func[[IntType], IntType]
        self.assertChecks(
            'let [x 1] (inc x)',
            Tuple.typed(IntType, [
                Symbol.typed(LET_TYPE, 'let'),
                List([
                    Symbol.typed(IntType, 'x'),
                    Number.typed(IntType, 1),
                ]),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Symbol.typed(IntType, 'x'),
                ]),
            ]),
            {'inc': inc_type},
        )

    def testInfer(self):
        inc_type = Func[[IntType], IntType]
        foo_type = Func[[NamedArg['arg', IntType]], IntType]
        self.assertChecks(
            """
            def foo
              inc #arg
            """,
            Tuple.typed(foo_type, [
                Symbol.typed(DEF_TYPE, 'def'),
                Symbol('foo'),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Placeholder.typed(TypeVar[IntType], 'arg'),
                ])
            ]),
            {'inc': inc_type},
        )

    def testRecord(self):
        inc_type = Func[[IntType], IntType]
        bar_type = RecordType[{'baz': IntType}]
        self.assertChecks(
            """
            inc bar.baz
            """,
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Tuple.typed(IntType, [
                    Symbol.typed(GET_TYPE, 'get'),
                    Symbol.typed(bar_type, 'bar'),
                    Symbol('baz'),
                ]),
            ]),
            {'inc': inc_type, 'bar': bar_type},
        )
        with self.assertRaises(KinkoTypeError):
            self.check('inc bar.unknown',
                       {'inc': inc_type, 'bar': bar_type})

    def testRecordInfer(self):
        bar_type = RecordType[{'baz': TypeVar[IntType]}]
        inc_type = Func[[IntType], IntType]
        foo_type = Func[[NamedArg['bar', bar_type]], IntType]
        self.assertChecks(
            """
            def foo
              inc #bar.baz
            """,
            Tuple.typed(foo_type, [
                Symbol.typed(DEF_TYPE, 'def'),
                Symbol('foo'),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Tuple.typed(TypeVar[IntType], [
                        Symbol.typed(GET_TYPE, 'get'),
                        Placeholder.typed(TypeVar[bar_type], 'bar'),
                        Symbol('baz'),
                    ]),
                ])
            ]),
            {'inc': inc_type},
        )

    def testIf(self):
        inc_type = Func[[IntType], IntType]
        self.assertChecks(
            """
            if (inc 1) (inc 2) (inc 3)
            """,
            Tuple.typed(Union[IntType,], [
                Symbol.typed(IF_TYPE, 'if'),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Number.typed(IntType, 1),
                ]),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Number.typed(IntType, 2),
                ]),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Number.typed(IntType, 3),
                ]),
            ]),
            {'inc': inc_type},
        )

    def testIfSome(self):
        inc_type = Func[[IntType], IntType]
        foo_type = RecordType[{'bar': Option[IntType]}]
        env = {'inc': inc_type, 'foo': foo_type}
        self.assertChecks(
            """
            if-some [x foo.bar] (inc x)
            """,
            Tuple.typed(Option[IntType], [
                Symbol.typed(IF_SOME_TYPE, 'if-some'),
                List([
                    Symbol('x'),
                    Tuple.typed(Option[IntType], [
                        Symbol.typed(GET_TYPE, 'get'),
                        Symbol.typed(foo_type, 'foo'),
                        Symbol('bar'),
                    ]),
                ]),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Symbol.typed(Union[IntType,], 'x'),
                ]),
            ]),
            env,
        )
        with self.assertRaises(KinkoTypeError):
            self.check('inc foo.bar', env)

    def testEach(self):
        inc_type = Func[[IntType], IntType]
        rec_type = RecordType[{'attr': IntType}]
        list_rec_type = ListType[rec_type]
        self.assertChecks(
            """
            each i collection
              inc i.attr
            """,
            Tuple.typed(ListType[IntType], [
                Symbol.typed(EACH_TYPE, 'each'),
                Symbol.typed(rec_type, 'i'),
                Symbol.typed(list_rec_type, 'collection'),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Tuple.typed(IntType, [
                        Symbol.typed(GET_TYPE, 'get'),
                        Symbol.typed(rec_type, 'i'),
                        Symbol('attr'),
                    ]),
                ]),
            ]),
            {'inc': inc_type, 'collection': list_rec_type},
        )

    def testList(self):
        foo_type = Func[[ListType[Union[IntType, StringType]]], IntType]
        self.assertChecks(
            """
            foo [1 2 3]
            """,
            Tuple.typed(IntType, [
                Symbol.typed(foo_type, 'foo'),
                List.typed(ListType[Union[IntType,]], [
                    Number.typed(IntType, 1),
                    Number.typed(IntType, 2),
                    Number.typed(IntType, 3),
                ]),
            ]),
            {'foo': foo_type},
        )
        self.assertChecks(
            """
            foo [1 2 "3"]
            """,
            Tuple.typed(IntType, [
                Symbol.typed(foo_type, 'foo'),
                List.typed(ListType[Union[IntType, StringType]], [
                    Number.typed(IntType, 1),
                    Number.typed(IntType, 2),
                    String.typed(StringType, '3'),
                ]),
            ]),
            {'foo': foo_type},
        )
        with self.assertRaises(KinkoTypeError):
            self.check('foo [1 2 "3"]',
                       {'foo': Func[[ListType[IntType]], IntType]})
