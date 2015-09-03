from itertools import chain

from .nodes import Tuple, Number, Keyword, String, List, Symbol, Placeholder
from .nodes import NodeVisitor
from .types import IntType, NamedArgMeta, StringType, ListType, VarArgsMeta
from .types import QuotedMeta, TypeVarMeta, TypeVar, Func, NamedArg, RecordType
from .types import RecordTypeMeta, BoolType, Union, ListTypeMeta, DictTypeMeta


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
    elif isinstance(t2, TypeVarMeta) and t2.__instance__ is None:
        pass
    else:
        if not isinstance(t1, type(t2)):
            raise KinkoTypeError('Unexpected type: {!r}, instead of: {!r}'
                                 .format(t1, t2))

        if isinstance(t1, RecordTypeMeta) and isinstance(t2, RecordTypeMeta):
            for key, value in t2.__items__.items():
                if key in t1.__items__:
                    unify(t1.__items__[key], value)
                else:
                    t1.__items__[key] = value
        elif isinstance(t1, ListTypeMeta):
            unify(t1.__item_type__, t2.__item_type__)
        elif isinstance(t1, DictTypeMeta):
            unify(t1.__key_type__, t2.__key_type__)
            unify(t1.__value_type__, t2.__value_type__)


def check_arg(arg, type_, env):
    if not isinstance(type_, QuotedMeta):
        arg = check(arg, env)
        unify(arg.__type__, type_)
        return arg
    else:
        return arg


def check_args(pos_args, kw_args, fn_type, env):
    pos_args, kw_args = pos_args[:], kw_args.copy()
    typed_pos_args, typed_kw_args = [], {}

    for i, arg_type in enumerate(fn_type.__args__):
        if isinstance(arg_type, NamedArgMeta):
            try:
                value = kw_args.pop(arg_type.__arg_name__)
            except KeyError:
                raise KinkoTypeError('Missing named argument: {!r}'
                                     .format(arg_type))
            else:
                typed_value = check_arg(value, arg_type.__arg_type__, env)
                typed_kw_args[arg_type.__arg_name__] = typed_value
        elif isinstance(arg_type, VarArgsMeta):
            typed_pos_args.append([
                check_arg(item, arg_type.__arg_type__, env)
                for item in pos_args
            ])
            pos_args = []
        else:
            try:
                value = pos_args.pop(0)
            except IndexError:
                raise KinkoTypeError('Missing positional argument: {!r}'
                                     .format(arg_type))
            else:
                typed_value = check_arg(value, arg_type, env)
                typed_pos_args.append(typed_value)

    if pos_args or kw_args:
        raise KinkoTypeError('More arguments than expected')

    return typed_pos_args, typed_kw_args


def check(node, env):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        pos_args, kw_args = split_args(args)

        fn_type = env[sym.name]
        sym = Symbol.typed(fn_type, sym.name)
        pos_args, kw_args = check_args(pos_args, kw_args,
                                       fn_type, env)
        if sym.name == 'let':
            pairs, let_body = pos_args
            assert isinstance(pairs, List), repr(pairs)
            let_env = env.copy()
            typed_pairs = []
            for let_sym, let_expr in zip(pairs.values[::2], pairs.values[1::2]):
                assert isinstance(let_sym, Symbol), repr(let_sym)
                let_expr = check(let_expr, env)
                let_sym = Symbol.typed(let_expr.__type__, let_sym.name)
                let_env[let_sym.name] = let_sym.__type__
                typed_pairs.append(let_sym)
                typed_pairs.append(let_expr)
            let_body = [check(item, let_env) for item in let_body]
            pos_args = [List(typed_pairs)] + let_body
            result_type = let_body[-1].__type__

        elif sym.name == 'def':
            def_sym, def_body = pos_args
            assert isinstance(def_sym, Symbol), repr(def_sym)
            visitor = _PlaceholdersExtractor()
            [visitor.visit(n) for n in def_body]
            ph_names = visitor.placeholders
            def_env = env.copy()
            for ph_name in ph_names:
                def_env[ph_name] = TypeVar[None]
            def_body = [check(item, def_env) for item in def_body]
            pos_args = [def_sym] + def_body
            def_args = [NamedArg[ph_name, def_env[ph_name].__instance__]
                        for ph_name in ph_names]
            result_type = Func[def_args, def_body[-1].__type__]

        elif sym.name == 'get':
            obj, attr = pos_args
            obj = check(obj, env)
            assert isinstance(attr, Symbol)
            unify(obj.__type__, RecordType[{attr.name: TypeVar[None]}])
            pos_args = obj, attr
            result_type = get_type(obj).__items__[attr.name]

        elif sym.name == 'if':
            expr, then_, else_ = pos_args
            expr = check(expr, env)
            unify(expr.__type__, BoolType)
            then_ = check(then_, env)
            else_ = check(else_, env)
            pos_args = expr, then_, else_
            result_type = Union[then_.__type__, else_.__type__]

        elif sym.name == 'each':
            item_sym, item_col, each_body = pos_args
            assert isinstance(item_sym, Symbol)
            item_sym = Symbol.typed(get_type(item_col).__item_type__,
                                    item_sym.name)
            each_env = env.copy()
            each_env[item_sym.name] = item_sym.__type__
            each_body = [check(item, each_env) for item in each_body]
            pos_args = [item_sym, item_col] + each_body
            result_type = ListType[each_body[-1].__type__]

        else:
            result_type = fn_type.__result__

        args = unsplit_args(pos_args, kw_args)
        return Tuple.typed(result_type, [sym] + args)

    elif isinstance(node, Symbol):
        return Symbol.typed(env[node.name], node.name)

    elif isinstance(node, Placeholder):
        return Placeholder.typed(env[node.name], node.name)

    elif isinstance(node, String):
        return String.typed(StringType, node.value)

    elif isinstance(node, Number):
        return Number.typed(IntType, node.value)

    elif isinstance(node, List):
        return List.typed(ListType, node.values)

    raise NotImplementedError(repr(node))
