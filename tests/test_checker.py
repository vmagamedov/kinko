from unittest import TestCase
try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from kinko.nodes import Tuple, Symbol, Number, Node, Keyword, List, Placeholder
from kinko.types import Func, IntType, NamedArg, Quoted, VarArgs, TypeVar
from kinko.types import TypingMetaBase
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


INC_TYPE = Func[[IntType], IntType]
INC2_TYPE = Func[[IntType, NamedArg['step', IntType]], IntType]
LET_TYPE = Func[[Quoted, VarArgs[Quoted]], None]  # FIXME
DEF_TYPE = Func[[Quoted, VarArgs[Quoted]], None]


class TestChecker(ParseMixin, TestCase):
    env = {
        'inc': INC_TYPE,
        'inc2': INC2_TYPE,
        'let': LET_TYPE,
        'def': DEF_TYPE,
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

    def assertChecks(self, src, typed):
        self.assertEqual(check(self.parse_expr(src), self.env), typed)

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
        self.assertChecks(
            'inc 1',
            Tuple.typed(IntType, [Symbol.typed(INC_TYPE, 'inc'),
                                  Number.typed(IntType, 1)]),
        )
        self.assertChecks(
            'inc2 1 :step 2',
            Tuple.typed(IntType, [Symbol.typed(INC2_TYPE, 'inc2'),
                                  Number.typed(IntType, 1),
                                  Keyword('step'), Number.typed(IntType, 2)]),
        )
        with self.assertRaises(KinkoTypeError):
            check(self.parse_expr('inc "foo"'), self.env)

    def testLet(self):
        self.assertChecks(
            'let [x 1] (inc x)',
            Tuple.typed(IntType, [
                Symbol.typed(LET_TYPE, 'let'),
                List([
                    Symbol.typed(IntType, 'x'),
                    Number.typed(IntType, 1),
                ]),
                Tuple.typed(IntType, [
                    Symbol.typed(INC_TYPE, 'inc'),
                    Symbol.typed(IntType, 'x'),
                ]),
            ]),
        )

    def testTypeVar(self):
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
                    Symbol.typed(INC_TYPE, 'inc'),
                    Placeholder.typed(TypeVar[IntType], 'arg'),
                ])
            ]),
        )
