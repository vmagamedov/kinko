from itertools import chain

from .nodes import Tuple, Number, Keyword, String, List, Symbol
from .types import IntType, NamedArgMeta, StringType, ListType, VarArgsMeta
from .types import QuotedMeta


class KinkoTypeError(TypeError):
    pass


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


def check_type(var, expected_type):
    if type(var.__type__) is not type(expected_type):
        raise KinkoTypeError('Unexpected type: {!r}, instead of: {!r}'
                             .format(var.__type__, expected_type))


def check_arg(value, type_, env):
    if not isinstance(type_, QuotedMeta):
        value = check(value, env)
        check_type(value, type_)
        return value
    else:
        return value


def check_args(pos_args, kw_args, op_type, env):
    pos_args, kw_args = pos_args[:], kw_args.copy()
    typed_pos_args, typed_kw_args = [], {}

    for i, arg_type in enumerate(op_type.__args__):
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

        op_type = env[sym.name]
        sym = Symbol.typed(op_type, sym.name)
        pos_args, kw_args = check_args(pos_args, kw_args,
                                       op_type, env)
        if sym.name == 'let':
            pairs, let_body = pos_args
            let_env = env.copy()
            typed_pairs = []
            for let_sym, let_expr in zip(pairs.values[::2], pairs.values[1::2]):
                let_expr = check(let_expr, env)
                let_sym = Symbol.typed(let_expr.__type__, let_sym.name)
                let_env[let_sym.name] = let_sym.__type__
                typed_pairs.append(let_sym)
                typed_pairs.append(let_expr)
            let_body = [check(item, let_env) for item in let_body]
            pos_args = [List(typed_pairs)] + let_body
            result_type = let_body[-1].__type__
        else:
            result_type = op_type.__result__

        args = unsplit_args(pos_args, kw_args)
        return Tuple.typed(result_type, [sym] + args)

    elif isinstance(node, Symbol):
        return Symbol.typed(env[node.name], node.name)

    elif isinstance(node, String):
        return String.typed(StringType, node.value)

    elif isinstance(node, Number):
        return Number.typed(IntType, node.value)

    elif isinstance(node, List):
        return List.typed(ListType, node.values)

    raise NotImplementedError(repr(node))
