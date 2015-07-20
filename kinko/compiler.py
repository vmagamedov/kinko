from . import nodes as N
import ast as P
import astor


def compile_dotname(dotname):
    assert isinstance(dotname.item, N.Symbol), dotname
    val = P.Name(dotname.item.name, True)
    for attr in dotname.attrs:
        assert isinstance(attr, N.Symbol), dotname
        val = P.Attribute(val, attr.name, True)
    return val

def compile_expr(expr):
    if isinstance(expr, N.Tuple):
        return compile_tuple(expr)
    elif isinstance(expr, N.Dotname):
        return compile_dotname(expr)
    elif isinstance(expr, N.Number):
        return P.Number(expr.value)
    elif isinstance(expr, N.String):
        return P.Str(expr.value)
    else:
        raise NotImplementedError(expr)


def compile_tuple(tup):
    return P.Call(P.Name(tup.symbol.name, True),
         list(map(compile_expr, tup.args)), [],
         None, None)


def compile_body(lst):
    return list(map(compile_tuple, lst))

def compile_template(lst):
    body = compile_body(lst)
    return astor.to_source(P.Module(body=body))
