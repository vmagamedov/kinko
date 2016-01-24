from json.encoder import encode_basestring

from slimit import ast as js

from ...utils import split_args
from ...nodes import Tuple, Symbol, Placeholder, String, Number
from ...compat import text_type
from ...checker import HTML_TAG_TYPE, GET_TYPE, IF1_TYPE, IF2_TYPE, JOIN1_TYPE
from ...checker import JOIN2_TYPE, get_type, DEF_TYPE
from ...checker import normalize_args
from ...constant import SELF_CLOSING_ELEMENTS

from ..common import Environ, returns_markup


def _str(value):
    return js.String(encode_basestring(value))


def _text(value):
    return js.ExprStatement(js.FunctionCall(js.Identifier('text'), [value]))


def _ctx_var(value):
    return js.BracketAccessor(js.Identifier('ctx'), _str(value))


def _yield_writes(env, node):
    if returns_markup(node):
        for item in compile_stmt(env, node):
            yield item
    else:
        yield _text(compile_expr(env, node))


def _el_open(tag, key=None, attrs=None, self_close=False):
    fn = 'elementVoid' if self_close else 'elementOpen'
    return js.ExprStatement(js.FunctionCall(js.Identifier(fn), [
        _str(tag),
        _str(key or ''),
        js.Array([]),
        js.Array(attrs or []),
    ]))


def _el_close(tag):
    return js.ExprStatement(js.FunctionCall(js.Identifier('elementClose'),
                                            [_str(tag)]))


def compile_if1_expr(env, node, test, then_):
    test_expr = compile_expr(env, test)
    then_expr = compile_expr(env, then_)
    else_expr = js.Null(None)
    return js.Conditional(test_expr, then_expr, else_expr)


def compile_if2_expr(env, node, test, then_, else_):
    test_expr = compile_expr(env, test)
    then_expr = compile_expr(env, then_)
    else_expr = compile_expr(env, else_)
    return js.Conditional(test_expr, then_expr, else_expr)


def compile_get_expr(env, node, obj, attr):
    obj_expr = compile_expr(env, obj)
    return js.BracketAccessor(obj_expr, _str(attr.name))


def compile_func_expr(env, node, *norm_args):
    sym, args = node.values[0], node.values[1:]
    pos_args, kw_args = split_args(args)

    name_expr = js.DotAccessor(js.Identifier('builtins'),
                               js.Identifier(sym.name))

    compiled_args = [compile_expr(env, value)
                     for value in pos_args]

    compiled_args.append(js.Object([
        js.Label(_str(text_type(key)), compile_expr(env, value))
        for key, value in kw_args.items()
    ]))
    return js.FunctionCall(name_expr, compiled_args)


EXPR_TYPES = {
    IF1_TYPE: compile_if1_expr,
    IF2_TYPE: compile_if2_expr,
    GET_TYPE: compile_get_expr,
}


def compile_expr(env, node):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        assert sym.__type__
        pos_args, kw_args = split_args(args)
        norm_args = normalize_args(sym.__type__, pos_args, kw_args)
        proc = EXPR_TYPES.get(sym.__type__, compile_func_expr)
        return proc(env, node, *norm_args)

    elif isinstance(node, Symbol):
        if node.name in env:
            return js.Identifier(env[node.name])
        else:
            return _ctx_var(node.name)

    elif isinstance(node, Placeholder):
        return js.Identifier(env[node.name])

    elif isinstance(node, String):
        return _str(text_type(node.value))

    elif isinstance(node, Number):
        return js.Number(text_type(node.value))

    else:
        raise TypeError('Unable to compile {!r} of type {!r} as expression'
                        .format(node, type(node)))


def compile_def_stmt(env, node, name_sym, body):
    args = [a.__arg_name__ for a in get_type(node).__args__]
    with env.push(args):
        yield js.FuncDecl(js.Identifier(name_sym.name),
                          [js.Identifier(env[arg]) for arg in args],
                          list(compile_stmts(env, body)))


def compile_html_tag_stmt(env, node, attrs, body):
    tag_name = node.values[0].name
    self_closing = tag_name in SELF_CLOSING_ELEMENTS

    compiled_attrs = []
    for key, value in attrs.items():
        compiled_attrs.append(_str(text_type(key)))
        compiled_attrs.append(compile_expr(env, value))

    yield _el_open(tag_name, None, compiled_attrs,
                   self_close=self_closing)
    if self_closing:
        assert not body, ('Positional args are not expected in the '
                          'self-closing elements')
        return

    for arg in body:
        for item in _yield_writes(env, arg):
            yield item

    yield _el_close(tag_name)


def compile_if1_stmt(env, node, test, then_):
    test_expr = compile_expr(env, test)
    yield js.If(test_expr, js.Block(list(_yield_writes(env, then_))), None)


def compile_if2_stmt(env, node, test, then_, else_):
    test_expr = compile_expr(env, test)
    yield js.If(test_expr, js.Block(list(_yield_writes(env, then_))),
                js.Block(list(_yield_writes(env, else_))))


def compile_join1_stmt(env, node, col):
    for value in col.values:
        for item in _yield_writes(env, value):
            yield item


def compile_join2_stmt(env, node, sep, col):
    for i, value in enumerate(col.values):
        if i:
            yield _text(_str(sep.value))
        for item in _yield_writes(env, value):
            yield item


STMT_TYPES = {
    DEF_TYPE: compile_def_stmt,
    HTML_TAG_TYPE: compile_html_tag_stmt,
    IF1_TYPE: compile_if1_stmt,
    IF2_TYPE: compile_if2_stmt,
    JOIN1_TYPE: compile_join1_stmt,
    JOIN2_TYPE: compile_join2_stmt,
}


def compile_stmt(env, node):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        assert sym.__type__

        pos_args, kw_args = split_args(args)
        norm_args = normalize_args(sym.__type__, pos_args, kw_args)

        proc = STMT_TYPES[sym.__type__]
        for item in proc(env, node, *norm_args):
            yield item

    elif isinstance(node, Symbol):
        if node.name in env:
            yield _text(js.Identifier(env[node.name]))
        else:
            yield _text(_ctx_var(node.name))

    elif isinstance(node, Placeholder):
        yield js.ExprStatement(js.FunctionCall(js.Identifier(env[node.name]),
                                               []))

    elif isinstance(node, String):
        yield _text(js.String(node.value))

    elif isinstance(node, Number):
        yield _text(js.Number(node.value))

    else:
        raise TypeError('Unable to compile {!r} of type {!r} as statement'
                        .format(node, type(node)))


def compile_stmts(env, nodes):
    for node in nodes:
        for item in compile_stmt(env, node):
            yield item


def compile_module(body):
    env = Environ()
    mod = js.Program(list(compile_stmts(env, body.values)))
    return mod


def dumps(node):
    return node.to_ecma() + '\n'
