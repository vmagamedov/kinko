from itertools import chain
from contextlib import contextmanager
from collections import namedtuple, deque, defaultdict

from .refs import ArgRef, FieldRef, ItemRef, Reference, is_from_arg
from .nodes import Tuple, Number, Keyword, String, List, Symbol, Placeholder
from .nodes import NodeVisitor, NodeTransformer
from .types import IntType, NamedArgMeta, StringType, ListType, VarArgsMeta
from .types import TypeVarMeta, TypeVar, Func, NamedArg, Record, TypeRefMeta
from .types import RecordMeta, BoolType, Union, ListTypeMeta, DictTypeMeta
from .types import TypingMeta, UnionMeta, Nothing, Option, VarArgs, FuncMeta
from .types import TypeTransformer, Markup, VarNamedArgs, VarNamedArgsMeta
from .types import MarkupMeta
from .utils import VarsGen
from .errors import Errors, UserError
from .compat import zip_longest
from .constant import HTML_ELEMENTS


class SyntaxError(UserError):
    pass


class TypeCheckError(UserError):
    pass


class SignatureMismatch(UserError):
    pass


class Environ(object):

    def __init__(self, defs=None, errors=None):
        self.defs = defs or {}
        self.vars = deque([{}])
        self._root = TypeVar[None]
        self.errors = Errors() if errors is None else errors

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
            type_ = self.defs[key]
            if isinstance(type_, FuncMeta):
                return type_
            else:
                var = TypeVar[type_]
                var.__backref__ = FieldRef(None, key)
                return var

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
            return node.clone_with(sep.join([self.ns, name]))
        else:
            return node

    def visit_tuple(self, node):
        if node.values[0].name == 'def':
            (def_sym, name_sym), body = node.values[:2], node.values[2:]
            qualified_name = '/'.join([self.ns, name_sym.name])
            name_sym = name_sym.clone_with(qualified_name)
            values = ([self.visit(def_sym), name_sym] +
                      [self.visit(i) for i in body])
            return node.clone_with(values)
        else:
            return super(NamesResolver, self).visit_tuple(node)


class NamesUnResolver(NodeTransformer):

    def __init__(self, ns):
        self.ns = ns

    def visit_symbol(self, node):
        if node.ns == self.ns:
            return node.clone_with('./{}'.format(node.rel))
        return node.clone()

    def visit_tuple(self, node):
        if node.values[0].name == 'def':
            (def_sym, name_sym), body = node.values[:2], node.values[2:]
            name_sym = name_sym.clone_with(name_sym.rel)
            return node.clone_with([self.visit(def_sym), name_sym] +
                                   [self.visit(i) for i in body])
        return super(NamesUnResolver, self).visit_tuple(node)


def def_types(node):
    assert isinstance(node, List), type(node)
    return {d.values[1].name: Unchecked(d, False)
            for d in node.values if isinstance(d.values[1], Symbol)}


def collect_defs(nodes):
    return List(chain.from_iterable(node.values for node in nodes))


def split_defs(node):
    mapping = defaultdict(list)
    for defn in node.values:
        name_sym = defn.values[1]
        mapping[name_sym.ns].append(defn)
    return {ns: List(body)
            for ns, body in mapping.items()}


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
        if type_.__instance__ is None:
            if type_ not in self._mapping:
                self._mapping[type_] = TypeVar[None]
            return self._mapping[type_]
        return self.visit(type_.__instance__)


def get_type(node):
    t = node.__type__
    while isinstance(t, TypeVarMeta):
        t = t.__instance__
    return t


def contains_markup(type_):
    def recur_check(t):
        if isinstance(t, UnionMeta):
            return any(recur_check(st) for st in t.__types__)
        else:
            return isinstance(t, MarkupMeta)
    return recur_check(type_)


def returns_markup(node):
    type_ = get_type(node)
    return contains_markup(type_)


def item_ref(backref):
    v = TypeVar[None]
    v.__backref__ = ItemRef(backref)
    return v


def field_refs(backref, names):
    mapping = {}
    for name in names:
        v = TypeVar[None]
        v.__backref__ = FieldRef(backref, name)
        mapping[name] = v
    return mapping


def unify(t1, t2, backref=None):
    """Unify `t1` to match `t2`

    After unification `t1` should be equal to `t2` or `t1` would be
    a subtype of `t2`.

    `t1` may contain type variables. If `t1` comes from arguments and
    contains a record, this record will be extended. `t1`, also, may contain
    type references.

    `t2` can not contain bound type variables, only unbound type variables
    are allowed - they're represent polymorphic types in the function signature.
    `t2`, also, can not contain type references.
    """
    if isinstance(t1, TypeRefMeta):
        assert t1.__ref__ is not None, 'Unbound type reference {!r}'.format(t1)
        unify(t1.__ref__(), t2, backref)

    elif isinstance(t2, TypeRefMeta):
        assert False  # type references are not expected in t2

    elif isinstance(t2, TypeVarMeta) and t2.__instance__ is None:
        assert isinstance(backref, Reference) or backref is None, repr(backref)
        t2.__instance__ = t1
        t2.__backref__ = backref

    elif isinstance(t2, TypeVarMeta):
        assert False  # bound type-vars are not expected in t2

    elif isinstance(t1, TypeVarMeta) and t1.__instance__ is None:
        backref = t1 if t1.__backref__ else backref
        if backref and isinstance(t2, RecordMeta):
            t1.__instance__ = Record[field_refs(backref, t2.__items__)]
            unify(t1, t2, backref)
        elif backref and isinstance(t2, ListTypeMeta):
            t1.__instance__ = ListType[item_ref(backref)]
            unify(t1, t2, backref)
        elif backref and isinstance(t2, DictTypeMeta):
            raise NotImplementedError('TODO')
        else:
            t1.__instance__ = t2

    elif isinstance(t1, TypeVarMeta):
        backref = t1 if t1.__backref__ else backref
        try:
            unify(t1.__instance__, t2, backref)
        except TypeCheckError:
            if (
                backref and is_from_arg(backref) and
                not isinstance(t1.__instance__, TypingMeta) and
                isinstance(t2, type(t1.__instance__))
            ):
                t1.__instance__ = t2
            else:
                raise

    else:
        if isinstance(t1, UnionMeta):
            # all types from t1 union should unify with t2
            for t in t1.__types__:
                unify(t, t2, backref)
            return
        elif isinstance(t2, UnionMeta):
            # t1 should unify with at least one type from t2 union
            for t in t2.__types__:
                try:
                    unify(t1, t, backref)
                except TypeCheckError:
                    continue
                else:
                    return
            # not unified
        else:
            if isinstance(t1, type(t2)):
                if isinstance(t1, RecordMeta):
                    s1, s2 = set(t1.__items__), set(t2.__items__)
                    if backref and is_from_arg(backref):
                        t1.__items__.update(field_refs(backref, s2 - s1))
                    else:
                        if s2 - s1:
                            raise TypeCheckError('Missing keys {} in {!r}'
                                                 .format(s2 - s1, t1))
                    for k, v2 in t2.__items__.items():
                        unify(t1.__items__[k], v2, FieldRef(backref, k))
                    return

                elif isinstance(t1, ListTypeMeta):
                    unify(t1.__item_type__, t2.__item_type__, ItemRef(backref))
                    return

                elif isinstance(t1, DictTypeMeta):
                    unify(t1.__key_type__, t2.__key_type__, backref)
                    unify(t1.__value_type__, t2.__value_type__, backref)
                    return

                if not isinstance(t1, TypingMeta):
                    # means simple type with nullary constructor
                    return

        raise TypeCheckError('Unexpected type: {!r}, instead of: {!r}'
                             .format(t1, t2))


def split_args(args):
    pos_args, kw_args = [], {}
    i = enumerate(args)
    try:
        while True:
            arg_pos, arg = next(i)
            if isinstance(arg, Keyword):
                try:
                    value_pos, _ = next(i)
                except StopIteration:
                    raise TypeError('Missing named argument value')
                else:
                    kw_args[arg.name] = value_pos
            else:
                pos_args.append(arg_pos)
    except StopIteration:
        return pos_args, kw_args


def normalize_args(fn_type, args, pos_args, kw_args):
    pos_args, kw_args = list(pos_args), dict(kw_args)
    norm_args = []
    norm_args_pos = []
    missing_arg = False
    for arg_type in fn_type.__args__:
        if isinstance(arg_type, NamedArgMeta):
            try:
                value_pos = kw_args.pop(arg_type.__arg_name__)
            except KeyError:
                missing_arg = True
                break
            else:
                norm_args.append(args[value_pos])
                norm_args_pos.append(value_pos)
        elif isinstance(arg_type, VarArgsMeta):
            norm_args.append([args[pos] for pos in pos_args])
            norm_args_pos.append(list(pos_args))
            del pos_args[:]
        elif isinstance(arg_type, VarNamedArgsMeta):
            norm_args.append({k: args[v] for k, v in kw_args.items()})
            norm_args_pos.append(kw_args.copy())
            kw_args.clear()
        else:
            try:
                value_pos = pos_args.pop(0)
            except IndexError:
                missing_arg = True
                break
            else:
                norm_args.append(args[value_pos])
                norm_args_pos.append(value_pos)
    if pos_args or kw_args or missing_arg:
        raise SignatureMismatch
    else:
        return norm_args, norm_args_pos


def match_fn(fn_types, args):
    pos_args, kw_args = split_args(args)
    for fn_type in fn_types:
        try:
            norm_args, norm_args_pos = \
                normalize_args(fn_type, args, pos_args, kw_args)
        except SignatureMismatch:
            continue
        else:
            return fn_type, norm_args, norm_args_pos
    else:
        raise TypeCheckError('Function signature mismatch')


def restore_args(fn_type, args, norm_args, norm_args_pos):
    args_map = {}
    _norm_args = list(norm_args)
    _norm_args_pos = list(norm_args_pos)
    for arg_type in fn_type.__args__:
        if isinstance(arg_type, NamedArgMeta):
            value = _norm_args.pop(0)
            value_pos = _norm_args_pos.pop(0)
            args_map[value_pos - 1] = args[value_pos - 1]  # keyword
            args_map[value_pos] = value
        elif isinstance(arg_type, VarArgsMeta):
            values = _norm_args.pop(0)
            values_pos = _norm_args_pos.pop(0)
            for v, v_pos in zip(values, values_pos):
                args_map[v_pos] = v
        elif isinstance(arg_type, VarNamedArgsMeta):
            values_map = _norm_args.pop(0)
            values_pos = _norm_args_pos.pop(0)
            for key in values_map.keys():
                value = values_map[key]
                value_pos = values_pos[key]
                args_map[value_pos - 1] = args[value_pos - 1]  # keyword
                args_map[value_pos] = value
        else:
            value = _norm_args.pop(0)
            value_pos = _norm_args_pos.pop(0)
            args_map[value_pos] = value
    assert not _norm_args
    assert len(args_map) == len(args)
    return [args_map[i] for i in range(len(args))]


def check_arg(arg, type_, env):
    arg = check(arg, env)
    with env.errors.location(arg.location):
        unify(arg.__type__, type_)
    return arg


_StringLike = Union[Nothing, IntType, StringType]

_MarkupLike = Union[_StringLike, Markup]


__var = VarsGen()

LET_TYPE = Func[[__var.bindings, __var.expr], __var.result]

DEF_TYPE = Func[[__var.name, __var.body], __var.result]

GET_TYPE = Func[[Record[{}], __var.key], __var.result]

IF1_TYPE = Func[[BoolType, __var.then_], __var.result]
IF2_TYPE = Func[[BoolType, __var.then_, __var.else_], __var.result]
IF3_TYPE = Func[[BoolType, NamedArg['then', __var.then_],
                 NamedArg['else', __var.else_]],
                __var.result]


EACH_TYPE = Func[[__var.symbol, ListType[__var.item], _MarkupLike],
                 Markup]

IF_SOME1_TYPE = Func[[__var.bind, __var.then_], __var.result]
IF_SOME2_TYPE = Func[[__var.bind, __var.then_, __var.else_], __var.result]
IF_SOME3_TYPE = Func[[__var.bind, NamedArg['then', __var.then_],
                      NamedArg['else', __var.else_]],
                     __var.result]

HTML_TAG_TYPE = Func[[VarNamedArgs[_StringLike], VarArgs[_MarkupLike]],
                     Markup]

JOIN1_TYPE = Func[[ListType[_MarkupLike]], Markup]
JOIN2_TYPE = Func[[StringType, ListType[_StringLike]], StringType]

del __var


def prune(t):
    while isinstance(t, TypeVarMeta):
        t = t.__instance__
    return t


def arg_var(name):
    t = TypeVar[None]
    t.__backref__ = ArgRef(name)
    return t


def ctx_var(t, name):
    v = TypeVar[t]
    v.__backref__ = FieldRef(None, name)
    return v


def check_let(fn_type, env, bindings, expr):
    with env.errors.location(bindings.location):
        if not isinstance(bindings, List):
            raise SyntaxError('Variable bindings should be a list')
    let_vars = {}
    typed_bindings = []
    for let_sym, let_expr in zip_longest(bindings.values[::2],
                                         bindings.values[1::2]):
        with env.errors.location(let_sym.location):
            if not isinstance(let_sym, Symbol):
                raise SyntaxError('Even elements of "let" bindings '
                                  'should be a symbol')
            if let_expr is None:
                raise SyntaxError('Variable does not have a corresponding '
                                  'value after it')
        let_expr = check(let_expr, env)
        let_sym = let_sym.clone_with(let_sym.name, type=let_expr.__type__)
        let_vars[let_sym.name] = let_sym.__type__
        typed_bindings.append(let_sym)
        typed_bindings.append(let_expr)
    with env.push(let_vars):
        typed_expr = check(expr, env)
    unify(fn_type.__result__, typed_expr.__type__)
    return bindings.clone_with(typed_bindings), typed_expr


def check_def(fn_type, env, sym, body):
    if not isinstance(sym, Symbol):
        with env.errors.location(sym.location):
            raise SyntaxError('Function name should be defined using symbol')
    visitor = _PlaceholdersExtractor()
    visitor.visit(body)
    kw_arg_names = visitor.placeholders
    def_vars = {name: arg_var(name) for name in kw_arg_names}
    with env.push(def_vars), env.errors.func_ctx(sym.ns, sym.rel):
        body = check(body, env)
    args = [NamedArg[name, def_vars[name]] for name in kw_arg_names]
    unify(fn_type.__result__, Func[args, body.__type__])
    fn_type = _FreshVars().visit(fn_type)
    # register new definition type in env
    env.define(sym.name, fn_type.__result__)
    return sym, body


def check_get(fn_type, env, obj, attr):
    obj = check(obj, env)
    if not isinstance(attr, Symbol):
        with env.errors.location(attr.location):
            raise SyntaxError('Record field name should be specified by symbol')
    with env.errors.location(obj.location):
        unify(obj.__type__, Record[{attr.name: fn_type.__result__}])
    return obj, attr


def check_if1(fn_type, env, test, then_):
    test = check(test, env)
    with env.errors.location(test.location):
        unify(test.__type__, BoolType)
    then_ = check(then_, env)
    unify(fn_type.__result__, Option[then_.__type__])
    return test, then_


def check_if2(fn_type, env, test, then_, else_):
    test = check(test, env)
    with env.errors.location(test.location):
        unify(test.__type__, BoolType)
    then_ = check(then_, env)
    else_ = check(else_, env)
    unify(fn_type.__result__, Union[then_.__type__, else_.__type__])
    return test, then_, else_


def check_each(fn_type, env, var, col, body):
    if not isinstance(var, Symbol):
        with env.errors.location(var.location):
            raise SyntaxError('Variable name should be specified by symbol')
    col = check(col, env)
    var_type = TypeVar[None]
    with env.errors.location(col.location):
        unify(col.__type__, ListType[var_type])
    var = var.clone_with(var.name, type=var_type)
    with env.push({var.name: var_type}):
        body = check(body, env)
    return var, col, body


def _check_if_some_bind(env, bind):
    if not isinstance(bind, List):
        with env.errors.location(bind.location):
            raise SyntaxError('Variable binding should be specified by list')
    if len(bind.values) != 2:
        with env.errors.location(bind.location):
            raise SyntaxError('Variable binding should be specified using '
                              'list with exactly two elements')
    bind_sym, bind_expr = bind.values
    if not isinstance(bind_sym, Symbol):
        with env.errors.location(bind_sym.location):
            raise SyntaxError('Variable name should be specified by symbol')
    bind_expr = check(bind_expr, env)
    bind_expr_type = get_type(bind_expr)
    if (
        isinstance(bind_expr_type, UnionMeta) and
        Nothing in bind_expr_type.__types__
    ):
        inner_expr_type = Union[bind_expr_type.__types__ - {Nothing}]
    else:
        env.errors.warn(bind_expr.location,
                        'if-some check is not necessary, expression type '
                        'is not optional')
        inner_expr_type = bind_expr_type
    return bind_sym, bind_expr, inner_expr_type


def check_if_some1(fn_type, env, bind, then_):
    bind_sym, bind_expr, inner_expr_type = _check_if_some_bind(env, bind)
    with env.push({bind_sym.name: inner_expr_type}):
        then_ = check(then_, env)
    unify(fn_type.__result__, Option[then_.__type__])
    return bind.clone_with([bind_sym, bind_expr]), then_


def check_if_some2(fn_type, env, bind, then_, else_):
    bind_sym, bind_expr, inner_expr_type = _check_if_some_bind(env, bind)
    with env.push({bind_sym.name: inner_expr_type}):
        then_ = check(then_, env)
        else_ = check(else_, env)
    unify(fn_type.__result__, Union[then_.__type__, else_.__type__])
    return bind.clone_with([bind_sym, bind_expr]), then_, else_


FN_TYPES = {
    LET_TYPE: check_let,
    DEF_TYPE: check_def,
    GET_TYPE: check_get,
    IF1_TYPE: check_if1,
    IF2_TYPE: check_if2,
    IF3_TYPE: check_if2,
    EACH_TYPE: check_each,
    IF_SOME1_TYPE: check_if_some1,
    IF_SOME2_TYPE: check_if_some2,
    IF_SOME3_TYPE: check_if_some2,
}


BUILTINS = {
    'let': [LET_TYPE],
    'def': [DEF_TYPE],
    'get': [GET_TYPE],
    'if': [IF1_TYPE, IF2_TYPE, IF3_TYPE],
    'each': [EACH_TYPE],
    'if-some': [IF_SOME1_TYPE, IF_SOME2_TYPE, IF_SOME3_TYPE],
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
            with env.errors.location(sym.location):
                raise TypeCheckError('Unknown function name: {}'
                                     .format(sym.name))
    else:
        if isinstance(fn_type, Unchecked):
            if fn_type.in_progress:
                with env.errors.location(sym.location):
                    raise TypeCheckError('Recursive call of the function {!r}'
                                         .format(sym.name))
            else:
                env.define(sym.name, fn_type._replace(in_progress=True))
                check(fn_type.node, env)
                # after checking dependent node it should be registered
                # in environ and recursive check_expr call should work
                return check_expr(node, env)
        else:
            fn_types = [fn_type]

    with env.errors.location(sym.location):
        matched_fn_type, norm_args, norm_args_pos = match_fn(fn_types, args)
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

    uni_args = restore_args(matched_fn_type, args, uni_norm_args, norm_args_pos)

    t_sym = sym.clone_with(sym.name, type=matched_fn_type)
    return node.clone_with([t_sym] + uni_args,
                           type=fresh_fn_type.__result__)


def check(node, env):
    if isinstance(node, Tuple):
        return check_expr(node, env)

    elif isinstance(node, Symbol):
        return node.clone_with(node.name, type=env[node.name])

    elif isinstance(node, Placeholder):
        return node.clone_with(node.name, type=env[node.name])

    elif isinstance(node, String):
        return node.clone_with(node.value, type=StringType)

    elif isinstance(node, Number):
        return node.clone_with(node.value, type=IntType)

    elif isinstance(node, List):
        values = [check(v, env) for v in node.values]
        type_ = ListType[Union[(v.__type__ for v in values)]]
        return node.clone_with(values, type=type_)

    raise NotImplementedError(repr(node))
