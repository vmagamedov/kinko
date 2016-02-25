from kinko.refs import NamedArgRef
from kinko.nodes import Tuple, Symbol, Number, Keyword, List, Placeholder
from kinko.nodes import String
from kinko.types import Func, IntType, StringType, NamedArg, TypeVar, Markup
from kinko.types import Record, ListType, Union, DictType, Option
from kinko.types import VarArgs, VarNamedArgs, BoolType, RecordMeta
from kinko.checker import Environ, check, KinkoTypeError, EACH_TYPE, _FreshVars
from kinko.checker import LET_TYPE, DEF_TYPE, GET_TYPE, IF2_TYPE, IF_SOME1_TYPE
from kinko.checker import unify, NamesResolver, def_types
from kinko.checker import match_fn, restore_args, HTML_TAG_TYPE

from .base import TestCase, NODE_EQ_PATCHER, TYPE_EQ_PATCHER
from .test_parser import ParseMixin


class TestChecker(ParseMixin, TestCase):
    ctx = [NODE_EQ_PATCHER, TYPE_EQ_PATCHER]

    def parse_expr(self, src):
        return self.parse(src).values[0]

    def check(self, src, env=None):
        return check(self.parse_expr(src), Environ(env))

    def assertChecks(self, src, typed, extra_env=None):
        self.assertEqual(self.check(src, extra_env), typed)

    def testMatchFn(self):
        # basic args
        self.assertEqual(
            match_fn([Func[[IntType, IntType], IntType]],
                     [1, 2]),
            (Func[[IntType, IntType], IntType], [1, 2])
        )
        with self.assertRaises(KinkoTypeError):
            match_fn([Func[[IntType, IntType], IntType]],
                     [1])
        with self.assertRaises(KinkoTypeError):
            match_fn([Func[[IntType, IntType], IntType]],
                     [1, 2, 3])
        # named args
        self.assertEqual(
            match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                     [1, Keyword('foo'), 2]),
            (Func[[IntType, NamedArg['foo', IntType]], IntType], [1, 2])
        )
        self.assertEqual(
            match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                     [Keyword('foo'), 2, 1]),
            (Func[[IntType, NamedArg['foo', IntType]], IntType], [1, 2])
        )
        with self.assertRaises(KinkoTypeError):
            match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                     [1])
        with self.assertRaises(KinkoTypeError):
            match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                     [1, Keyword('foo'), 2, Keyword('bar'), 3])
        # variable args
        self.assertEqual(
            match_fn([Func[[IntType, VarArgs[IntType]], IntType]],
                     [1, 2, 3]),
            (Func[[IntType, VarArgs[IntType]], IntType], [1, [2, 3]])
        )
        # variable named args
        self.assertEqual(
            match_fn([Func[[IntType, VarNamedArgs[IntType]], IntType]],
                     [1, Keyword('foo'), 2, Keyword('bar'), 3]),
            (Func[[IntType, VarNamedArgs[IntType]], IntType],
             [1, {'foo': 2, 'bar': 3}])
        )

    def testFreshVars(self):
        v1, v2 = TypeVar[None], TypeVar[None]
        t = TypeVar[Record[{'foo': v1, 'bar': v2, 'baz': v1}]]
        fresh_t = _FreshVars().visit(t)
        self.assertIsInstance(fresh_t, RecordMeta)
        self.assertEqual(fresh_t.__items__['foo'], TypeVar[None])
        self.assertEqual(fresh_t.__items__['bar'], TypeVar[None])
        self.assertEqual(fresh_t.__items__['baz'], TypeVar[None])
        self.assertIsNot(fresh_t.__items__['foo'], fresh_t.__items__['bar'])
        self.assertIs(fresh_t.__items__['foo'], fresh_t.__items__['baz'])
        self.assertIsNot(fresh_t.__items__['foo'], v1)
        self.assertIsNot(fresh_t.__items__['bar'], v2)
        self.assertIsNot(fresh_t.__items__['baz'], v1)

    def testRestoreArgs(self):
        self.assertEqual(
            restore_args(Func[[IntType, IntType], IntType],
                         [1, 2]),
            [1, 2],
        )
        self.assertEqual(
            restore_args(Func[[IntType, NamedArg['foo', IntType]], IntType],
                         [1, 2]),
            [1, Keyword('foo'), 2],
        )
        self.assertEqual(
            restore_args(Func[[IntType, VarArgs[IntType]], IntType],
                         [1, [2, 3, 4]]),
            [1, 2, 3, 4],
        )
        self.assertEqual(
            restore_args(Func[[IntType, VarNamedArgs[IntType]], IntType],
                         [1, {'foo': 2}]),
            [1, Keyword('foo'), 2],
        )

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

    def testUnifySubtype(self):
        a = TypeVar[BoolType]
        a.__backref__ = NamedArgRef('arg')
        unify(a, IntType)
        self.assertIsInstance(IntType, type(a.__instance__))
        self.assertEqual(a.__instance__, IntType)

        b = TypeVar[None]
        b.__backref__ = NamedArgRef('arg')
        unify(b, Record[{'a': BoolType, 'b': BoolType}])
        unify(b, Record[{'b': IntType, 'c': IntType}])
        self.assertEqual(b, Record[{
            'a': BoolType, 'b': IntType, 'c': IntType,
        }])

    def testUnifyUnion(self):
        a = Union[StringType, IntType]
        unify(a, a)
        with self.assertRaises(KinkoTypeError):
            unify(a, StringType)
        unify(IntType, a)
        unify(StringType, a)

    def testUnifyRecordType(self):
        rec_type = Record[{'a': TypeVar[None]}]
        unify(rec_type, Record[{'a': IntType}])
        self.assertEqual(rec_type, Record[{'a': IntType}])

        with self.assertRaises(KinkoTypeError):
            unify(Record[{'a': IntType}], Record[{'a': StringType}])

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
                    Placeholder.typed(IntType, 'arg'),
                ])
            ]),
            {'inc': inc_type},
        )

    def testRecord(self):
        inc_type = Func[[IntType], IntType]
        bar_type = Record[{'baz': IntType}]
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
        bar_type = Record[{'baz': IntType}]
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
                    Tuple.typed(IntType, [
                        Symbol.typed(GET_TYPE, 'get'),
                        Placeholder.typed(bar_type, 'bar'),
                        Symbol('baz'),
                    ]),
                ])
            ]),
            {'inc': inc_type},
        )

    def testRecordInferWithSubTyping(self):
        n = self.check(
            """
            def foo
              f1 #bar.baz
              f2 #bar
              f3 #bar.baz
            """,
            {'f1': Func[[BoolType], StringType],
             'f2': Func[[Record[{'baz': TypeVar[None]}]], StringType],
             'f3': Func[[IntType], StringType]},
        )
        self.assertEqual(
            n.__type__.__instance__,
            Func[[NamedArg['bar', Record[{'baz': IntType}]]],
                 Markup],
        )

    def testIf(self):
        inc_type = Func[[IntType], IntType]
        self.assertChecks(
            """
            if (inc 1) (inc 2) (inc 3)
            """,
            Tuple.typed(Union[IntType, ], [
                Symbol.typed(IF2_TYPE, 'if'),
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
        foo_type = Record[{'bar': Option[IntType]}]
        env = {'inc': inc_type, 'foo': foo_type}
        self.assertChecks(
            """
            if-some [x foo.bar] (inc x)
            """,
            Tuple.typed(Option[IntType], [
                Symbol.typed(IF_SOME1_TYPE, 'if-some'),
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
                    Symbol.typed(Union[IntType, ], 'x'),
                ]),
            ]),
            env,
        )
        with self.assertRaises(KinkoTypeError):
            self.check('inc foo.bar', env)

    def testEach(self):
        inc_type = Func[[IntType], IntType]
        rec_type = Record[{'attr': IntType}]
        list_rec_type = ListType[rec_type]
        self.assertChecks(
            """
            each i collection
              inc i.attr
            """,
            Tuple.typed(Markup, [
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
                List.typed(ListType[Union[IntType, ]], [
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

    def testHTMLTags(self):
        self.assertChecks(
            """
            div :foo "bar"
              span "Some Text"
            """,
            Tuple.typed(Markup, [
                Symbol.typed(HTML_TAG_TYPE, 'div'),
                Keyword('foo'),
                String.typed(StringType, 'bar'),
                Tuple.typed(Markup, [
                    Symbol.typed(HTML_TAG_TYPE, 'span'),
                    String.typed(StringType, 'Some Text'),
                ]),
            ]),
        )

    def testDependent(self):
        node = self.parse("""
        def foo
          ./bar :arg "value"

        def bar
          #arg
        """)
        node = NamesResolver('test').visit(node)
        env = Environ(def_types(node))
        node = check(node, env)

        foo_expr, bar_expr = node.values
        self.assertEqual(foo_expr.__type__,
                         Func[[], StringType])
        self.assertEqual(bar_expr.__type__,
                         Func[[NamedArg['arg', TypeVar[None]]],
                              TypeVar[None]])
        # checks that TypeVar instance is the same
        self.assertIs(bar_expr.__type__.__instance__.__args__[0].__arg_type__,
                      bar_expr.__type__.__instance__.__result__)
