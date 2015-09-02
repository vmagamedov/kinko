from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from kinko.nodes import Tuple, Symbol, Number, Node, Keyword, List, Placeholder
from kinko.types import Func, IntType, NamedArg, Quoted, VarArgs, TypeVar, Union
from kinko.types import TypingMetaBase, RecordType, ListType
from kinko.checker import check, split_args, unsplit_args, KinkoTypeError

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


LET_TYPE = Func[[Quoted, VarArgs[Quoted]], TypeVar[None]]
DEF_TYPE = Func[[Quoted, VarArgs[Quoted]], TypeVar[None]]
GET_TYPE = Func[[Quoted, Quoted], TypeVar[None]]
IF_TYPE = Func[[Quoted, Quoted, Quoted], TypeVar[None]]
EACH_TYPE = Func[[Quoted, ListType[None], VarArgs[Quoted]], TypeVar[None]]


class TestChecker(ParseMixin, TestCase):
    default_env = {
        'let': LET_TYPE,
        'def': DEF_TYPE,
        'get': GET_TYPE,
        'if': IF_TYPE,
        'each': EACH_TYPE,
    }

    def parse_expr(self, src):
        return self.parse(src).values[0]

    def setUp(self):
        self.node_patcher = patch.multiple(Node, __eq__=node_eq, __ne__=node_ne)
        self.node_patcher.start()
        self.type_patcher = patch.multiple(TypingMetaBase,
                                           __eq__=type_eq, __ne__=type_ne)
        self.type_patcher.start()

    def tearDown(self):
        self.type_patcher.stop()
        self.node_patcher.stop()

    def assertChecks(self, src, typed, extra_env=None):
        env = dict(self.default_env, **(extra_env or {}))
        self.assertEqual(check(self.parse_expr(src), env), typed)

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

    def testSimple(self):
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
            check(self.parse_expr('inc "foo"'), {'inc': inc_type})

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
        data_type = RecordType[{'attr': TypeVar[IntType]}]
        inc_type = Func[[IntType], IntType]
        foo_type = Func[[NamedArg['arg', data_type]], IntType]
        self.assertChecks(
            """
            def foo
              inc #arg.attr
            """,
            Tuple.typed(foo_type, [
                Symbol.typed(DEF_TYPE, 'def'),
                Symbol('foo'),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Tuple.typed(TypeVar[IntType], [
                        Symbol.typed(GET_TYPE, 'get'),
                        Placeholder.typed(TypeVar[data_type], 'arg'),
                        Symbol('attr'),
                    ]),
                ])
            ]),
            {'inc': inc_type},
        )

    def testRecordUnify(self):
        data_type = RecordType[{'attr1': TypeVar[IntType],
                                'attr2': TypeVar[IntType]}]
        sum_type = Func[[IntType, IntType], IntType]
        foo_type = Func[[NamedArg['arg', data_type]], IntType]
        self.assertChecks(
            """
            def foo
              sum #arg.attr1 #arg.attr2
            """,
            Tuple.typed(foo_type, [
                Symbol.typed(DEF_TYPE, 'def'),
                Symbol('foo'),
                Tuple.typed(IntType, [
                    Symbol.typed(sum_type, 'sum'),
                    Tuple.typed(TypeVar[IntType], [
                        Symbol.typed(GET_TYPE, 'get'),
                        Placeholder.typed(TypeVar[data_type], 'arg'),
                        Symbol('attr1'),
                    ]),
                    Tuple.typed(TypeVar[IntType], [
                        Symbol.typed(GET_TYPE, 'get'),
                        Placeholder.typed(TypeVar[data_type], 'arg'),
                        Symbol('attr2'),
                    ]),
                ])
            ]),
            {'sum': sum_type},
        )

    def testEnvVar(self):
        foo_type = Func[[], IntType]
        inc_type = Func[[IntType], IntType]
        self.assertChecks(
            """
            def foo
              inc var
            """,
            Tuple.typed(foo_type, [
                Symbol.typed(DEF_TYPE, 'def'),
                Symbol('foo'),
                Tuple.typed(IntType, [
                    Symbol.typed(inc_type, 'inc'),
                    Symbol.typed(IntType, 'var'),
                ]),
            ]),
            {'inc': inc_type, 'var': IntType},
        )

    def testIf(self):
        inc_type = Func[[IntType], IntType]
        self.assertChecks(
            """
            if (inc 1) (inc 2) (inc 3)
            """,
            Tuple.typed(Union[IntType, IntType], [
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
            {'inc': inc_type,
             'collection': list_rec_type},
        )
