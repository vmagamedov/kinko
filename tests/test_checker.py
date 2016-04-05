from textwrap import dedent

import py.test

from kinko.refs import ArgRef
from kinko.nodes import Tuple, Symbol, Number, Keyword, List, Placeholder
from kinko.nodes import String
from kinko.types import Func, IntType, StringType, NamedArg, TypeVar, Markup
from kinko.types import Record, ListType, Union, DictType, Option
from kinko.types import VarArgs, VarNamedArgs, BoolType, RecordMeta
from kinko.errors import Errors
from kinko.checker import Environ, check, TypeCheckError, EACH_TYPE, _FreshVars
from kinko.checker import LET_TYPE, DEF_TYPE, GET_TYPE, IF2_TYPE, IF_SOME1_TYPE
from kinko.checker import unify, NamesResolver, def_types, IF1_TYPE, IF3_TYPE
from kinko.checker import match_fn, restore_args, HTML_TAG_TYPE, IF_SOME2_TYPE
from kinko.checker import IF_SOME3_TYPE

from .base import NODE_EQ_PATCHER, TYPE_EQ_PATCHER
from .test_parser import parse, LocationChecker


def check_expr(src, env=None, errors=None):
    node = check(parse(src).values[0], Environ(env, errors))
    LocationChecker().visit(node)
    return node


def check_eq(first, second):
    with NODE_EQ_PATCHER, TYPE_EQ_PATCHER:
        assert first == second


def check_expr_type(src, typed, env=None):
    node = check_expr(src, env)
    check_eq(node, typed)


def check_errors(src, env, msg, fragment):
    src = dedent(src).strip()
    errors = Errors()
    try:
        check_expr(src, env, errors)
    except TypeCheckError:
        e, = errors.list
        assert msg in e.message
        assert src[e.location.start.offset:e.location.end.offset] == fragment
    else:
        raise AssertionError('Error not raised')


def test_match_fn():
    # basic args
    check_eq(
        match_fn([Func[[IntType, IntType], IntType]],
                 [1, 2]),
        (Func[[IntType, IntType], IntType], [1, 2], [0, 1])
    )
    with py.test.raises(TypeCheckError):
        match_fn([Func[[IntType, IntType], IntType]],
                 [1])
    with py.test.raises(TypeCheckError):
        match_fn([Func[[IntType, IntType], IntType]],
                 [1, 2, 3])
    # named args
    check_eq(
        match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                 [1, Keyword('foo'), 2]),
        (Func[[IntType, NamedArg['foo', IntType]], IntType], [1, 2], [0, 2])
    )
    check_eq(
        match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                 [Keyword('foo'), 2, 1]),
        (Func[[IntType, NamedArg['foo', IntType]], IntType], [1, 2], [2, 1])
    )
    with py.test.raises(TypeCheckError):
        match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                 [1])
    with py.test.raises(TypeCheckError):
        match_fn([Func[[IntType, NamedArg['foo', IntType]], IntType]],
                 [1, Keyword('foo'), 2, Keyword('bar'), 3])
    # variable args
    check_eq(
        match_fn([Func[[IntType, VarArgs[IntType]], IntType]],
                 [1, 2, 3]),
        (Func[[IntType, VarArgs[IntType]], IntType], [1, [2, 3]], [0, [1, 2]])
    )
    # variable named args
    check_eq(
        match_fn([Func[[IntType, VarNamedArgs[IntType]], IntType]],
                 [1, Keyword('foo'), 2, Keyword('bar'), 3]),
        (Func[[IntType, VarNamedArgs[IntType]], IntType],
         [1, {'foo': 2, 'bar': 3}], [0, {'foo': 2, 'bar': 4}])
    )


def test_fresh_vars():
    v1, v2 = TypeVar[None], TypeVar[None]
    t = TypeVar[Record[{'foo': v1, 'bar': v2, 'baz': v1}]]
    fresh_t = _FreshVars().visit(t)
    assert isinstance(fresh_t, RecordMeta)
    check_eq(fresh_t.__items__['foo'], TypeVar[None])
    check_eq(fresh_t.__items__['bar'], TypeVar[None])
    check_eq(fresh_t.__items__['baz'], TypeVar[None])
    assert fresh_t.__items__['foo'] is not fresh_t.__items__['bar']
    assert fresh_t.__items__['foo'] is fresh_t.__items__['baz']
    assert fresh_t.__items__['foo'] is not v1
    assert fresh_t.__items__['bar'] is not v2
    assert fresh_t.__items__['baz'] is not v1


def test_restore_args():
    check_eq(
        restore_args(Func[[IntType, IntType], IntType],
                     [1, 2],
                     [1, 2],
                     [0, 1]),
        [1, 2],
    )
    check_eq(
        restore_args(Func[[IntType, NamedArg['foo', IntType]], IntType],
                     [1, Keyword('foo'), 2],
                     [1, 2],
                     [0, 2]),
        [1, Keyword('foo'), 2],
    )
    check_eq(
        restore_args(Func[[IntType, VarArgs[IntType]], IntType],
                     [1, 2, 3, 4],
                     [1, [2, 3, 4]],
                     [0, [1, 2, 3]]),
        [1, 2, 3, 4],
    )
    check_eq(
        restore_args(Func[[IntType, VarNamedArgs[IntType]], IntType],
                     [1, Keyword('foo'), 2],
                     [1, {'foo': 3}],
                     [0, {'foo': 2}]),
        [1, Keyword('foo'), 3],
    )


def test_unify_type():
    unify(IntType, IntType)

    with py.test.raises(TypeCheckError):
        unify(IntType, StringType)


def test_unify_type_var():
    a = TypeVar[None]
    unify(a, IntType)
    check_eq(a.__instance__, IntType)

    b = TypeVar[None]
    unify(IntType, b)
    check_eq(b.__instance__, IntType)

    with py.test.raises(TypeCheckError):
        unify(TypeVar[IntType], StringType)


def test_unify_subtype():
    a = TypeVar[BoolType]
    a.__backref__ = ArgRef('arg')
    unify(a, IntType)
    assert isinstance(IntType, type(a.__instance__))
    check_eq(a.__instance__, IntType)

    b = TypeVar[None]
    b.__backref__ = ArgRef('arg')
    unify(b, Record[{'a': BoolType, 'b': BoolType}])
    unify(b, Record[{'b': IntType, 'c': IntType}])
    check_eq(b, Record[{
        'a': BoolType, 'b': IntType, 'c': IntType,
    }])


def test_unify_union():
    a = Union[StringType, IntType]
    unify(a, a)
    with py.test.raises(TypeCheckError):
        unify(a, StringType)
    unify(IntType, a)
    unify(StringType, a)


def test_unify_record():
    rec_type = Record[{'a': TypeVar[None]}]
    unify(rec_type, Record[{'a': IntType}])
    check_eq(rec_type, Record[{'a': IntType}])

    with py.test.raises(TypeCheckError):
        unify(Record[{'a': IntType}], Record[{'a': StringType}])


def test_unify_list():
    list_type = ListType[TypeVar[None]]
    unify(list_type, ListType[IntType])
    check_eq(list_type.__item_type__.__instance__, IntType)


def test_unify_dict():
    dict_type = DictType[TypeVar[None], TypeVar[None]]
    unify(dict_type, DictType[StringType, IntType])
    check_eq(dict_type.__key_type__.__instance__, StringType)
    check_eq(dict_type.__value_type__.__instance__, IntType)


def test_func():
    inc_type = Func[[IntType], IntType]
    check_expr_type(
        'inc 1',
        Tuple.typed(IntType, [Symbol.typed(inc_type, 'inc'),
                              Number.typed(IntType, 1)]),
        {'inc': inc_type},
    )

    inc_step_type = Func[[IntType, NamedArg['step', IntType]], IntType]
    check_expr_type(
        'inc-step 1 :step 2',
        Tuple.typed(IntType, [Symbol.typed(inc_step_type, 'inc-step'),
                              Number.typed(IntType, 1),
                              Keyword('step'), Number.typed(IntType, 2)]),
        {'inc-step': inc_step_type},
    )
    with py.test.raises(TypeCheckError):
        check_expr('inc "foo"', {'inc': inc_type})


def test_env_var():
    inc_type = Func[[IntType], IntType]
    check_expr_type(
        """
        inc var
        """,
        Tuple.typed(IntType, [
            Symbol.typed(inc_type, 'inc'),
            Symbol.typed(IntType, 'var'),
        ]),
        {'inc': inc_type, 'var': IntType},
    )


def test_let():
    inc_type = Func[[IntType], IntType]
    check_expr_type(
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


def test_infer():
    inc_type = Func[[IntType], IntType]
    foo_type = Func[[NamedArg['arg', IntType]], IntType]
    check_expr_type(
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


def test_record():
    inc_type = Func[[IntType], IntType]
    bar_type = Record[{'baz': IntType}]
    check_expr_type(
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
    with py.test.raises(TypeCheckError):
        check_expr('inc bar.unknown',
                   {'inc': inc_type, 'bar': bar_type})


def test_record_infer():
    bar_type = Record[{'baz': IntType}]
    inc_type = Func[[IntType], IntType]
    foo_type = Func[[NamedArg['bar', bar_type]], IntType]
    check_expr_type(
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


def test_record_infer_with_subtyping():
    n = check_expr(
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
    check_eq(
        n.__type__.__instance__,
        Func[[NamedArg['bar', Record[{'baz': IntType}]]],
             Markup],
    )


def test_if_then():
    inc_type = Func[[IntType], IntType]
    check_expr_type(
        """
        if (inc 1) (inc 2)
        """,
        Tuple.typed(Option[IntType], [
            Symbol.typed(IF1_TYPE, 'if'),
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Number.typed(IntType, 1),
            ]),
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Number.typed(IntType, 2),
            ]),
        ]),
        {'inc': inc_type},
    )


def test_if_then_else():
    inc_type = Func[[IntType], IntType]
    check_expr_type(
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


def test_if_named_then_else():
    inc_type = Func[[IntType], IntType]
    check_expr_type(
        """
        if (inc 1) :then (inc 2) :else (inc 3)
        """,
        Tuple.typed(Union[IntType, ], [
            Symbol.typed(IF3_TYPE, 'if'),
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Number.typed(IntType, 1),
            ]),
            Keyword('then'),
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Number.typed(IntType, 2),
            ]),
            Keyword('else'),
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Number.typed(IntType, 3),
            ]),
        ]),
        {'inc': inc_type},
    )


def test_if_some():
    inc_type = Func[[IntType], IntType]
    foo_type = Record[{'bar': Option[IntType]}]
    env = {'inc': inc_type, 'foo': foo_type}
    check_expr_type(
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
    with py.test.raises(TypeCheckError):
        check_expr('inc foo.bar', env)


def test_if_some_else():
    inc_type = Func[[IntType], IntType]
    dec_type = Func[[IntType], IntType]
    foo_type = Record[{'bar': Option[IntType]}]
    env = {'inc': inc_type, 'dec': dec_type, 'foo': foo_type}
    check_expr_type(
        """
        if-some [x foo.bar] (inc x) (dec x)
        """,
        Tuple.typed(Union[IntType, IntType], [
            Symbol.typed(IF_SOME2_TYPE, 'if-some'),
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
            Tuple.typed(IntType, [
                Symbol.typed(dec_type, 'dec'),
                Symbol.typed(Union[IntType, ], 'x'),
            ]),
        ]),
        env,
    )


def test_if_some_named_else():
    inc_type = Func[[IntType], IntType]
    dec_type = Func[[IntType], IntType]
    foo_type = Record[{'bar': Option[IntType]}]
    env = {'inc': inc_type, 'dec': dec_type, 'foo': foo_type}
    check_expr_type(
        """
        if-some [x foo.bar] :then (inc x) :else (dec x)
        """,
        Tuple.typed(Union[IntType, IntType], [
            Symbol.typed(IF_SOME3_TYPE, 'if-some'),
            List([
                Symbol('x'),
                Tuple.typed(Option[IntType], [
                    Symbol.typed(GET_TYPE, 'get'),
                    Symbol.typed(foo_type, 'foo'),
                    Symbol('bar'),
                ]),
            ]),
            Keyword('then'),
            Tuple.typed(IntType, [
                Symbol.typed(inc_type, 'inc'),
                Symbol.typed(Union[IntType, ], 'x'),
            ]),
            Keyword('else'),
            Tuple.typed(IntType, [
                Symbol.typed(dec_type, 'dec'),
                Symbol.typed(Union[IntType, ], 'x'),
            ]),
        ]),
        env,
    )


def test_each():
    inc_type = Func[[IntType], IntType]
    rec_type = Record[{'attr': IntType}]
    list_rec_type = ListType[rec_type]
    check_expr_type(
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


def test_list():
    foo_type = Func[[ListType[Union[IntType, StringType]]], IntType]
    check_expr_type(
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
    check_expr_type(
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
    with py.test.raises(TypeCheckError):
        check_expr('foo [1 2 "3"]',
                   {'foo': Func[[ListType[IntType]], IntType]})


def test_html_tags():
    check_expr_type(
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


def test_dependent():
    node = parse("""
    def foo
      ./bar :arg "value"

    def bar
      #arg
    """)
    node = NamesResolver('test').visit(node)
    env = Environ(def_types(node))
    node = check(node, env)

    foo_expr, bar_expr = node.values
    check_eq(foo_expr.__type__, Func[[], StringType])
    check_eq(bar_expr.__type__,
             Func[[NamedArg['arg', TypeVar[None]]],
                  TypeVar[None]])
    # checks that TypeVar instance is the same
    assert bar_expr.__type__.__instance__.__args__[0].__arg_type__ is \
        bar_expr.__type__.__instance__.__result__


def test_def_errors():
    check_errors(
        """
        def foo-mod/bar-func
          foo [1 2 "3"]
        """,
        {'foo': Func[[ListType[IntType]], IntType]},
        'Unexpected type',
        '[1 2 "3"]',
    )
