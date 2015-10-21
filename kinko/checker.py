from itertools import chain

from .nodes import Tuple, Number, Keyword, String, List, Symbol, Placeholder
from .nodes import NodeVisitor
from .types import IntType, NamedArgMeta, StringType, ListType, VarArgsMeta
from .types import TypeVarMeta, TypeVar, Func, NamedArg, RecordType
from .types import RecordTypeMeta, BoolType, Union, ListTypeMeta, DictTypeMeta
from .types import TypingMeta, UnionMeta, Nothing, Option, VarArgs
from .types import TypeTransformer


class KinkoTypeError(TypeError):
    pass


class _PlaceholdersExtractor(NodeVisitor):

    def __init__(self):
        # using list to preserve placeholders order for the tests
        self.placeholders = []

    def visit_placeholder(self, node):
        if node.name not in self.placeholders:
            self.placeholders.append(node.name)


def split_args(args):
    pos_args, kw_args = [], {}
    i = iter(args)
    try:
        while True:
            arg = next(i)
            if isinstance(arg, Keyword):
                try:
                    val = next(i)
                except StopIteration:
                    raise KinkoTypeError('Missing named argument value')
                else:
                    kw_args[arg.name] = val
            else:
                pos_args.append(arg)
    except StopIteration:
        return pos_args, kw_args


def unsplit_args(pos_args, kw_args):
    args = list(pos_args)
    args.extend(chain.from_iterable(
        (Keyword(k), v) for k, v in kw_args.items()
    ))
    return args


def get_type(node):
    t = node.__type__
    while isinstance(t, TypeVarMeta):
        t = t.__instance__
    return t


def unify(t1, t2):
    if isinstance(t1, TypeVarMeta):
        if t1.__instance__ is None:
            t1.__instance__ = t2
        else:
            unify(t1.__instance__, t2)
    elif isinstance(t2, TypeVarMeta):
        unify(t2, t1)
    else:
        if isinstance(t1, UnionMeta):
            # all types from t1 union should unify with t2
            for t in t1.__types__:
                unify(t, t2)
            return
        elif isinstance(t2, UnionMeta):
            # t1 should unify with at least one type from t2 union
            for t in t2.__types__:
                try:
                    unify(t1, t)
                except KinkoTypeError:
                    continue
                else:
                    return
            # not unified
        else:
            if isinstance(t1, type(t2)):
                if isinstance(t1, RecordTypeMeta):
                    if isinstance(t2, RecordTypeMeta):
                        for key, value in t2.__items__.items():
                            if key in t1.__items__:
                                unify(t1.__items__[key], value)
                            else:
                                t1.__items__[key] = value
                    return

                elif isinstance(t1, ListTypeMeta):
                    if isinstance(t2, ListTypeMeta):
                        unify(t1.__item_type__, t2.__item_type__)
                    return

                elif isinstance(t1, DictTypeMeta):
                    if isinstance(t2, DictTypeMeta):
                        unify(t1.__key_type__, t2.__key_type__)
                        unify(t1.__value_type__, t2.__value_type__)
                    return

                if not isinstance(t1, TypingMeta):
                    # means simple type with nullary constructor
                    return

        raise KinkoTypeError('Unexpected type: {!r}, instead of: {!r}'
                             .format(t1, t2))


class VarCtx(object):

    def __getattr__(self, name):
        if name in self.vars:
            return self.vars[name]
        else:
            var = self.vars[name] = TypeVar[None]
            return var

    def __enter__(self):
        self.vars = {}
        return self

    def __exit__(self, *exc_info):
        del self.vars


class FreshVars(TypeTransformer):

    def __init__(self):
        self._mapping = {}

    def visit_typevar(self, type_):
        if type_ not in self._mapping:
            self._mapping[type_] = TypeVar[None]
        return self._mapping[type_]


def match_fn(fn_types, args):
    _pos_args, _kw_args = split_args(args)

    for fn_type in fn_types:
        norm_args = []
        pos_args, kw_args = _pos_args[:], _kw_args.copy()
        for arg_type in fn_type.__args__:
            if isinstance(arg_type, NamedArgMeta):
                try:
                    value = kw_args.pop(arg_type.__arg_name__)
                except KeyError:
                    continue
                else:
                    norm_args.append(value)
            elif isinstance(arg_type, VarArgsMeta):
                norm_args.append(list(pos_args))
                del pos_args[:]
            else:
                try:
                    value = pos_args.pop(0)
                except IndexError:
                    continue
                else:
                    norm_args.append(value)
        if pos_args or kw_args:
            continue
        else:
            return fn_type, norm_args
    else:
        raise KinkoTypeError('Function signature didn\'t matches')


def restore_args(fn_type, norm_args):
    # TODO: preserve original args ordering
    args = []
    _norm_args = list(norm_args)
    for arg_type in fn_type.__args__:
        if isinstance(arg_type, NamedArgMeta):
            args.extend([Keyword(arg_type.__arg_name__), _norm_args.pop(0)])
        elif isinstance(arg_type, VarArgsMeta):
            args.extend(_norm_args.pop(0))
        else:
            args.append(_norm_args.pop(0))
    assert not _norm_args
    return args


def check_arg(arg, type_, env):
    arg = check(arg, env)
    unify(arg.__type__, type_)
    return arg


def check_let(fn_type, env, pairs, body):
    assert isinstance(pairs, List), repr(pairs)
    body_env = env.copy()
    typed_pairs = []
    for let_sym, let_expr in zip(pairs.values[::2], pairs.values[1::2]):
        assert isinstance(let_sym, Symbol), repr(let_sym)
        let_expr = check(let_expr, env)
        let_sym = Symbol.typed(let_expr.__type__, let_sym.name)
        body_env[let_sym.name] = let_sym.__type__
        typed_pairs.append(let_sym)
        typed_pairs.append(let_expr)
    typed_body = [check(item, body_env) for item in body]
    unify(fn_type.__result__, typed_body[-1].__type__)
    return List(typed_pairs), typed_body


def check_def(fn_type, env, sym, body):
    assert isinstance(sym, Symbol), repr(sym)
    visitor = _PlaceholdersExtractor()
    [visitor.visit(n) for n in body]
    ph_names = visitor.placeholders
    body_env = env.copy()
    for ph_name in ph_names:
        body_env[ph_name] = TypeVar[None]
    body = [check(item, body_env) for item in body]
    args = [NamedArg[ph_name, body_env[ph_name].__instance__]
            for ph_name in ph_names]
    unify(fn_type.__result__, Func[args, body[-1].__type__])
    return sym, body


def check_get(fn_type, env, obj, attr):
    obj = check(obj, env)
    assert isinstance(attr, Symbol)
    if isinstance(obj.__type__, TypeVarMeta):
        unify(obj.__type__, RecordType[{attr.name: TypeVar[None]}])
    try:
        result_type = get_type(obj).__items__[attr.name]
    except KeyError:
        raise KinkoTypeError('Trying to get unknown record '
                             'attribute: "{}"'.format(attr.name))
    else:
        unify(fn_type.__result__, result_type)
        return obj, attr


def check_if1(fn_type, env, test, then_):
    test = check(test, env)
    unify(test.__type__, BoolType)
    then_ = check(then_, env)
    unify(fn_type.__result__, Option[then_.__type__])
    return test, then_


def check_if2(fn_type, env, test, then_, else_):
    test = check(test, env)
    unify(test.__type__, BoolType)
    then_ = check(then_, env)
    else_ = check(else_, env)
    unify(fn_type.__result__, Union[then_.__type__, else_.__type__])
    return test, then_, else_


def check_each(fn_type, env, var, col, body):
    assert isinstance(var, Symbol)
    col = check(col, env)
    unify(col.__type__, ListType[TypeVar[None]])
    var = Symbol.typed(get_type(col).__item_type__, var.name)
    body_env = env.copy()
    body_env[var.name] = var.__type__
    body = [check(item, body_env) for item in body]
    unify(fn_type.__result__, ListType[body[-1].__type__])
    return var, col, body


def check_if_some1(fn_type, env, bindings, then_):
    assert isinstance(bindings, List)
    bind_sym, bind_expr = bindings.values
    assert isinstance(bind_sym, Symbol)
    bind_expr = check(bind_expr, env)
    bind_expr_type = get_type(bind_expr)
    then_env = env.copy()
    if (
        isinstance(bind_expr_type, UnionMeta) and
        Nothing in bind_expr_type.__types__
    ):
        then_env[bind_sym.name] = \
            Union[bind_expr_type.__types__ - {Nothing}]
    else:
        # TODO: warn that this check is not necessary
        then_env[bind_sym.name] = bind_expr_type
    then_ = check(then_, then_env)
    unify(fn_type.__result__, Option[then_.__type__])
    return List([bind_sym, bind_expr]), then_


def check_if_some2():
    raise NotImplementedError


with VarCtx() as var:
    LET_TYPE = Func[[var.pairs, VarArgs[var.body]], var.result]

    DEF_TYPE = Func[[var.name, VarArgs[var.body]], var.result]

    GET_TYPE = Func[[RecordType[{}], var.key], var.result]

    IF1_TYPE = Func[[BoolType, var.then_], var.result]
    IF2_TYPE = Func[[BoolType, var.then_, var.else_], var.result]

    EACH_TYPE = Func[[var.symbol, ListType[var.item], VarArgs[var.body]],
                     var.result]

    IF_SOME1_TYPE = Func[[var.test, var.then_], var.result]
    IF_SOME2_TYPE = Func[[var.test, var.then_, var.else_], var.result]


FN_TYPES = {
    LET_TYPE: check_let,
    DEF_TYPE: check_def,
    GET_TYPE: check_get,
    IF1_TYPE: check_if1,
    IF2_TYPE: check_if2,
    EACH_TYPE: check_each,
    IF_SOME1_TYPE: check_if_some1,
    IF_SOME2_TYPE: check_if_some2,
}


BUILTINS = {
    'let': [LET_TYPE],
    'def': [DEF_TYPE],
    'get': [GET_TYPE],
    'if': [IF1_TYPE, IF2_TYPE],
    'each': [EACH_TYPE],
    'if-some': [IF_SOME1_TYPE, IF_SOME2_TYPE],
}


def check_expr(node, env):
    sym, args = node.values[0], node.values[1:]

    fn_types = [env.get(sym.name)] if sym.name in env else BUILTINS[sym.name]
    fn_type, norm_args = match_fn(fn_types, args)
    fresh_fn_type = FreshVars().visit(fn_type)

    proc = FN_TYPES.get(fn_type)
    if proc:
        uni_norm_args = proc(fresh_fn_type, env, *norm_args)
    else:
        uni_norm_args = []
        for arg, arg_type in zip(norm_args, fresh_fn_type.__args__):
            if isinstance(arg_type, NamedArgMeta):
                arg = check_arg(arg, arg_type.__arg_type__, env)
            elif isinstance(arg_type, VarArgsMeta):
                arg = [check_arg(i, arg_type.__arg_type__, env)
                       for i in arg]
            else:
                arg = check_arg(arg, arg_type, env)
            uni_norm_args.append(arg)

    uni_args = restore_args(fn_type, uni_norm_args)

    return Tuple.typed(fresh_fn_type.__result__,
                       [Symbol.typed(fn_type, sym.name)] + uni_args)


def check(node, env):
    if isinstance(node, Tuple):
        return check_expr(node, env)

    elif isinstance(node, Symbol):
        return Symbol.typed(env[node.name], node.name)

    elif isinstance(node, Placeholder):
        return Placeholder.typed(env[node.name], node.name)

    elif isinstance(node, String):
        return String.typed(StringType, node.value)

    elif isinstance(node, Number):
        return Number.typed(IntType, node.value)

    elif isinstance(node, List):
        values = [check(v, env) for v in node.values]
        return List.typed(ListType[Union[(v.__type__ for v in values)]],
                          values)

    raise NotImplementedError(repr(node))
