from .scope import Scope
from .nodes import Tuple
from .types import Func, OutputType, SymbolType, CollectionType
from .types import VarArgs, DictType, StringType


def check_args(args, ftype, scope):
    # TODO: implement
    return args, scope


def check(expr, scope):
    if isinstance(expr, Tuple):
        if not expr.values:
            raise TypeError('Empty tuple')
        name_sym, rest = expr.values[0], expr.values[1:]
        func = scope.lookup(name_sym)
        if not isinstance(func, type(Func)):
            raise TypeError('Not a Func type')
        return check_expr(name_sym.name, func, rest, scope)
    raise TypeError('Unknown type: {!r}'.format(expr))


def check_expr(fname, ftype, args, scope):
    args, scope = check_args(args, ftype, scope)
    if fname == 'each':  # [var collection *body]
        var, col, body = args
        body_scope = Scope({var: col.__item_type__}, parent=scope)
        body, body_scope = check(body, body_scope)
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
    'div': Func[[DictType[StringType], VarArgs[OutputType]], OutputType],
    'each': Func[[SymbolType, CollectionType, VarArgs[OutputType]], OutputType],
}, None)
