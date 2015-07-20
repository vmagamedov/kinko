from . import nodes as N
from . import pyast as P


def compile_dotname(dotname):
    val = P.Name(dotname.name)
    for attr in dotname.attr:
        val = P.Attr(val, attr)
    return val

def compile_expr(expr):
    if isinstance(expr, N.Tuple):
        return compile_tuple(expr)
    elif isinstance(expr, N.Dotname):
        return compile_dotname(expr)
    elif isinstance(expr, N.Number):
        return P.Number(expr.value)
    elif isinstance(expr, N.String):
        escaped = expr.value.encode('unicode_escape').decode('ascii')
        return P.String('"' + escaped + '"')
    else:
        raise NotImplementedError(expr)

def separate(gen, tok):
    # 2to3 nodes are not very semantical, so we need commas and newlines
    iterator = iter(gen)
    yield next(iterator)
    for item in iterator:
        yield tok.clone()
        yield item

def compile_tuple(tup):
    return P.Call(P.Name(tup.symbol.name),
         args=list(separate(map(compile_expr, tup.args), P.Comma())))


def compile_body(lst):
    return list(separate(map(compile_tuple, lst), P.Newline()))

def compile_template(lst):
    body = compile_body(lst)
    return P.Suite(body)
