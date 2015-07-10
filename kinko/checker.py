from itertools import chain

from .scope import Scope
from .nodes import Tuple, Keyword
from .types import *


def split_args(args):
    pos_args, kw_args = [], {}
    i = iter(args)
    try:
        while True:
            arg = i.next()
            if isinstance(arg, Keyword):
                try:
                    val = i.next()
                except StopIteration:
                    raise TypeError('Missing named argument value')
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


def gen_func_type(placeholders):
    # TODO: implement
    return Func[[], None]


def check_arg(value, type_, scope):
    if not isinstance(type_, QuotedMeta):
        value, scope = check(value, scope)
        check_type(value, type_)
        return value, scope
    else:
        return type_(value), scope


def check_args(args, kwargs, ftype, scope):
    args, kwargs = list(args), dict(kwargs)
    checked_args, checked_kwargs = [], {}

    for arg in ftype.__args__:
        if isinstance(arg, NamedArgMeta):
            try:
                value = kwargs.pop(arg.__arg_name__)
            except KeyError:
                raise TypeError('Missing named argument: {!r}'.format(arg))
            else:
                value, scope = check_arg(value, arg.__arg_type__, scope)
                checked_kwargs[arg.__arg_name__] = value
        elif isinstance(arg, VarArgsMeta):
            varargs = []
            for item in args:
                item, scope = check_arg(item, arg.__arg_type__, scope)
                varargs.append(item)
            checked_args.append(varargs)
            args = []
        else:
            try:
                value = args.pop(0)
            except IndexError:
                raise TypeError('Missing positional argument: {!r}'.format(arg))
            else:
                value, scope = check_arg(value, arg, scope)
                checked_args.append(value)

    if args or kwargs:
        raise TypeError('More arguments than expected')

    return checked_args, checked_kwargs, scope


def check(node, scope):
    if isinstance(node, Tuple):
        if not node.values:
            raise TypeError('Empty tuple')
        name_sym, rest = node.values[0], node.values[1:]
        func = scope.lookup(name_sym)
        if not isinstance(func, FuncMeta):
            raise TypeError('Not a Func type')
        return check_expr(name_sym.name, func, rest, scope)
    raise TypeError('Unknown type: {!r}'.format(node))


def check_expr(fname, ftype, args, scope):
    pos_args, kw_args = split_args(args)
    pos_args, kw_args, scope = check_args(pos_args, kw_args, ftype, scope)

    if fname == 'each':
        var, col, quoted_body = pos_args
        body_scope = Scope({var.name: col.__item_type__}, parent=scope)
        body = []
        for item in quoted_body:
            item, body_scope = check_arg(item.__quoted_value__,
                                         item.__arg_type__, body_scope)
            body.append(item)
        scope = scope.add(body_scope)
        pos_args = var, col, body

    elif fname == 'def':
        name, quoted_body = pos_args
        body_scope = Scope({}, parent=scope)
        body = []
        for item in quoted_body:
            item, body_scope = check_arg(item.__quoted_value__,
                                         item.__arg_type__, body_scope)
            body.append(item)
        scope = scope.add(body_scope)
        scope = scope.define(name, gen_func_type(body_scope.placeholders))
        pos_args = name, body

    else:
        raise NotImplementedError

    args = unsplit_args(pos_args, kw_args)
    return Tuple.typed(ftype.__result__, *args), scope


def check_type(var, expected_type):
    if var.__type__ is not expected_type:
        raise TypeError('Unexpected type: {!r}, instead of: {!r}'
                        .format(var.__type__, expected_type))


global_scope = Scope({
    'div': Func[
        [DictType[StringType, StringType], VarArgs[OutputType]],
        OutputType,
    ],
    'each': Func[
        [SymbolType, CollectionType, VarArgs[Quoted[OutputType]]],
        OutputType,
    ],
    'def': Func[[SymbolType, VarArgs[Quoted[OutputType]]], Func],
}, None)
