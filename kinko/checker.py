from .scope import Scope
from .nodes import Tuple
from .types import *


def split_args(args):
    # TODO: implement
    return [], {}


def check_arg(value, type_, scope):
    if not isinstance(type_, QuotedMeta):
        value, scope = check(value, scope)
        check_type(value, type_)
        return value, scope
    else:
        return type_(value), scope


def check_args(args, ftype, scope):
    args_, kwargs_ = split_args(args)
    checked_args, checked_kwargs = [], {}

    for arg in ftype.__args__:
        if isinstance(arg, NamedArgMeta):
            try:
                value = kwargs_.pop(arg.__arg_name__)
            except KeyError:
                raise TypeError('Missing named argument: {!r}'.format(arg))
            else:
                value, scope = check_arg(value, arg.__arg_type__, scope)
                checked_kwargs[arg.__arg_name__] = value
        elif isinstance(arg, VarArgsMeta):
            varargs = []
            for item in args_:
                item, scope = check_arg(item, arg.__arg_type__, scope)
                varargs.append(item)
            checked_args.append(varargs)
            args_ = []
        else:
            try:
                value = args_.pop(0)
            except IndexError:
                raise TypeError('Missing positional argument: {!r}'.format(arg))
            else:
                value, scope = check_arg(value, arg, scope)
                checked_args.append(value)

    if args_ or kwargs_:
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
    args, kwargs, scope = check_args(args, ftype, scope)
    if fname == 'each':  # [var collection *body]
        var, col, quoted_body = args
        body_scope = Scope({var: col.__item_type__}, parent=scope)
        body = []
        for item in quoted_body:
            item, body_scope = check_arg(item.__quoted_value__,
                                         item.__arg_type__, body_scope)
            body.append(item)
        scope = scope.add(body_scope)
        args = var, col, body

    elif fname == 'div':  # [attrs *body]
        pass

    elif fname == 'def':  # [name *body]
        name, body = args
        body, body_scope = check(body, scope)
        scope = scope.add(body_scope)
        # FIXME: gen proper ftype from placeholders
        ftype = body_scope.placeholders
        scope = scope.define(name, ftype)
        args = name, body

    else:
        raise NotImplementedError

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
}, None)
