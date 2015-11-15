from itertools import chain
from contextlib import contextmanager
from collections import namedtuple, deque

from .refs import NamedArgRef, RecordFieldRef, ListItemRef
from .nodes import Tuple, Number, Keyword, String, List, Symbol, Placeholder
from .nodes import NodeVisitor, NodeTransformer
from .types import IntType, NamedArgMeta, StringType, ListType, VarArgsMeta
from .types import TypeVarMeta, TypeVar, Func, NamedArg, Record
from .types import RecordMeta, BoolType, Union, ListTypeMeta, DictTypeMeta
from .types import TypingMeta, UnionMeta, Nothing, Option, VarArgs
from .types import TypeTransformer, Markup, VarNamedArgs, VarNamedArgsMeta
from .utils import VarsGen, split_args
from .constant import HTML_ELEMENTS


class KinkoTypeError(TypeError):
    pass


class SignatureMismatch(TypeError):
    pass


class Environ(object):

    def __init__(self, defs=None):
        self.vars = deque([{}])
        self.defs = defs.copy() if defs else {}

    @contextmanager
    def push(self, mapping):
        self.vars.append(mapping)
        try:
            yield
        finally:
            self.vars.pop()

    def __getitem__(self, key):
        for d in reversed(self.vars):
            try:
                return d[key]
            except KeyError:
                continue
        else:
            return ctx_var(self.defs[key], key)

    def __contains__(self, key):
        return any(key in d for d in self.vars) or key in self.defs

    def define(self, name, value):
        self.defs[name] = value


class NamesResolver(NodeTransformer):

    def __init__(self, ns):
        self.ns = ns

    def visit_symbol(self, node):
        ns, sep, name = node.name.partition('/')
        if name and ns == '.':
            return Symbol(sep.join([self.ns, name]))
        else:
            return node

    def visit_tuple(self, node):
        if node.values[0].name == 'def':
            (def_sym, name_sym), body = node.values[:2], node.values[2:]
            qualified_name = '/'.join([self.ns, name_sym.name])
            return Tuple([self.visit(def_sym), Symbol(qualified_name)] +
                         [self.visit(i) for i in body])
        else:
            return super(NamesResolver, self).visit_tuple(node)


class DefsMappingVisitor(NodeVisitor):

    def __init__(self):
        self.mapping = {}

    def visit_tuple(self, node):
        if node.values[0].name == 'def':
            self.mapping[node.values[1].name] = node
        super(DefsMappingVisitor, self).visit_tuple(node)


class _PlaceholdersExtractor(NodeVisitor):

    def __init__(self):
        # using list to preserve placeholders order for the tests
        self.placeholders = []

    def visit_placeholder(self, node):
        if node.name not in self.placeholders:
            self.placeholders.append(node.name)


class _FreshVars(TypeTransformer):

    def __init__(self):
        self._mapping = {}

    def visit_typevar(self, type_):
        if type_ not in self._mapping:
            self._mapping[type_] = TypeVar[None]
        return self._mapping[type_]


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
                if isinstance(t1, RecordMeta):
                    if isinstance(t2, RecordMeta):
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


def normalize_args(fn_type, pos_args, kw_args):
    pos_args, kw_args = list(pos_args), dict(kw_args)
    norm_args = []
    missing_arg = False
    for arg_type in fn_type.__args__:
        if isinstance(arg_type, NamedArgMeta):
            try:
                value = kw_args.pop(arg_type.__arg_name__)
            except KeyError:
                missing_arg = True
                break
            else:
                norm_args.append(value)
        elif isinstance(arg_type, VarArgsMeta):
            norm_args.append(list(pos_args))
            del pos_args[:]
        elif isinstance(arg_type, VarNamedArgsMeta):
            norm_args.append(kw_args.copy())
            kw_args.clear()
        else:
            try:
                value = pos_args.pop(0)
            except IndexError:
                missing_arg = True
                break
            else:
                norm_args.append(value)
    if pos_args or kw_args or missing_arg:
        raise SignatureMismatch
    else:
        return norm_args


def match_fn(fn_types, args):
    pos_args, kw_args = split_args(args)
    for fn_type in fn_types:
        try:
            norm_args = normalize_args(fn_type, pos_args, kw_args)
        except SignatureMismatch:
            continue
        else:
            return fn_type, norm_args
    else:
        raise KinkoTypeError('Function signature mismatch')


def restore_args(fn_type, norm_args):
    # TODO: preserve original args ordering
    args = []
    _norm_args = list(norm_args)
    for arg_type in fn_type.__args__:
        if isinstance(arg_type, NamedArgMeta):
            args.extend((Keyword(arg_type.__arg_name__),
                         _norm_args.pop(0)))
        elif isinstance(arg_type, VarArgsMeta):
            args.extend(_norm_args.pop(0))
        elif isinstance(arg_type, VarNamedArgsMeta):
            args.extend(chain.from_iterable(
                (Keyword(key), value)
                for key, value in _norm_args.pop(0).items()
            ))
        else:
            args.append(_norm_args.pop(0))
    assert not _norm_args
    return args


def check_arg(arg, type_, env):
    arg = check(arg, env)
    unify(arg.__type__, type_)
    return arg


_StringLike = Union[Nothing, IntType, StringType]

_MarkupLike = Union[_StringLike, Markup]


__var = VarsGen()

LET_TYPE = Func[[__var.pairs, VarArgs[__var.body]], __var.result]

DEF_TYPE = Func[[__var.name, VarArgs[__var.body]], __var.result]

GET_TYPE = Func[[Record[{}], __var.key], __var.result]

IF1_TYPE = Func[[BoolType, __var.then_], __var.result]
IF2_TYPE = Func[[BoolType, __var.then_, __var.else_], __var.result]

EACH_TYPE = Func[[__var.symbol, ListType[__var.item], VarArgs[_MarkupLike]],
                 Markup]

IF_SOME1_TYPE = Func[[__var.test, __var.then_], __var.result]
IF_SOME2_TYPE = Func[[__var.test, __var.then_, __var.else_], __var.result]

HTML_TAG_TYPE = Func[[VarNamedArgs[_StringLike], VarArgs[_MarkupLike]],
                     Markup]

JOIN1_TYPE = Func[[ListType[_MarkupLike]], Markup]
JOIN2_TYPE = Func[[StringType, ListType[_MarkupLike]], Markup]

del __var


def prune(t):
    while isinstance(t, TypeVarMeta):
        t = t.__instance__
    return t


def arg_var(name):
    t = TypeVar[None]
    t.__backref__ = NamedArgRef(name)
    return t


def ctx_var(t, name):
    v = TypeVar[t]
    v.__backref__ = RecordFieldRef(None, name)
    return v


def check_let(fn_type, env, pairs, body):
    assert isinstance(pairs, List), repr(pairs)
    let_vars = {}
    typed_pairs = []
    for let_sym, let_expr in zip(pairs.values[::2], pairs.values[1::2]):
        assert isinstance(let_sym, Symbol), repr(let_sym)
        let_expr = check(let_expr, env)
        let_sym = Symbol.typed(let_expr.__type__, let_sym.name)
        let_vars[let_sym.name] = let_sym.__type__
        typed_pairs.append(let_sym)
        typed_pairs.append(let_expr)
    with env.push(let_vars):
        typed_body = [check(item, env) for item in body]
    unify(fn_type.__result__, typed_body[-1].__type__)
    return List(typed_pairs), typed_body


def check_def(fn_type, env, sym, body):
    assert isinstance(sym, Symbol), repr(sym)
    visitor = _PlaceholdersExtractor()
    [visitor.visit(n) for n in body]
    kw_arg_names = visitor.placeholders
    def_vars = {name: arg_var(name) for name in kw_arg_names}
    with env.push(def_vars):
        body = [check(item, env) for item in body]
    args = [NamedArg[name, def_vars[name]] for name in kw_arg_names]
    unify(fn_type.__result__, Func[args, body[-1].__type__])
    # register new definition type in env
    env.define(sym.name, fn_type.__result__.__instance__)
    return sym, body


def check_get(fn_type, env, obj, attr):
    obj = check(obj, env)
    assert isinstance(attr, Symbol)
    if isinstance(obj.__type__, TypeVarMeta):
        unify(obj.__type__, Record[{attr.name: TypeVar[None]}])
    try:
        result_type = get_type(obj).__items__[attr.name]
    except KeyError:
        raise KinkoTypeError('Trying to get unknown record '
                             'attribute: "{}"'.format(attr.name))
    else:
        unify(fn_type.__result__, result_type)
        fn_type.__result__.__backref__ = RecordFieldRef(obj.__type__, attr.name)
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
    var = Symbol.typed(TypeVar[get_type(col).__item_type__], var.name)
    var.__type__.__backref__ = ListItemRef(col.__type__)
    with env.push({var.name: var.__type__}):
        body = [check(item, env) for item in body]
    return var, col, body


def check_if_some1(fn_type, env, bindings, then_):
    assert isinstance(bindings, List)
    bind_sym, bind_expr = bindings.values
    assert isinstance(bind_sym, Symbol)
    bind_expr = check(bind_expr, env)
    bind_expr_type = get_type(bind_expr)
    if (
        isinstance(bind_expr_type, UnionMeta) and
        Nothing in bind_expr_type.__types__
    ):
        then_expr_type = Union[bind_expr_type.__types__ - {Nothing}]
    else:
        # TODO: warn that this check is not necessary
        then_expr_type = bind_expr_type
    with env.push({bind_sym.name: then_expr_type}):
        then_ = check(then_, env)
    unify(fn_type.__result__, Option[then_.__type__])
    return List([bind_sym, bind_expr]), then_


def check_if_some2():
    raise NotImplementedError


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
    'join': [JOIN1_TYPE, JOIN2_TYPE],
}
for tag_name in HTML_ELEMENTS:
    BUILTINS[tag_name] = [HTML_TAG_TYPE]


Unchecked = namedtuple('Unchecked', 'node in_progress')


def check_expr(node, env):
    sym, args = node.values[0], node.values[1:]

    try:
        fn_type = prune(env[sym.name])
    except KeyError:
        try:
            fn_types = BUILTINS[sym.name]
        except KeyError:
            raise KinkoTypeError('Unknown function name: {}'.format(sym.name))
    else:
        if isinstance(fn_type, Unchecked):
            if fn_type.in_progress:
                raise KinkoTypeError('Recursive call of the {} function'
                                     .format(sym.name))
            else:
                env.define(sym.name, fn_type._replace(in_progress=True))
                check(fn_type.node, env)
                # after checking dependent node it should be registered
                # in environ and recursive check_expr call should work
                return check_expr(node, env)
        else:
            fn_types = [fn_type]

    matched_fn_type, norm_args = match_fn(fn_types, args)
    fresh_fn_type = _FreshVars().visit(matched_fn_type)

    proc = FN_TYPES.get(matched_fn_type)
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
            elif isinstance(arg_type, VarNamedArgsMeta):
                arg = {k: check_arg(v, arg_type.__arg_type__, env)
                       for k, v in arg.items()}
            else:
                arg = check_arg(arg, arg_type, env)
            uni_norm_args.append(arg)

    uni_args = restore_args(matched_fn_type, uni_norm_args)

    return Tuple.typed(fresh_fn_type.__result__,
                       [Symbol.typed(matched_fn_type, sym.name)] + uni_args)


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
