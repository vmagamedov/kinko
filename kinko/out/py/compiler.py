from __future__ import absolute_import

from ast import NodeTransformer, iter_fields, copy_location
from ast import fix_missing_locations

import astor

from ...types import NamedArgMeta, VarArgsMeta, VarNamedArgsMeta
from ...nodes import String, Tuple, Symbol, List, Number, Placeholder
from ...nodes import NodeVisitor
from ...compat import text_type
from ...checker import split_args, normalize_args, DEF_TYPE, HTML_TAG_TYPE
from ...checker import IF1_TYPE, IF2_TYPE, EACH_TYPE, JOIN1_TYPE, JOIN2_TYPE
from ...checker import GET_TYPE, get_type
from ...constant import SELF_CLOSING_ELEMENTS

from ..common import Environ, returns_markup

from . import ast as py


def _write(value):
    return py.Expr(py.Call(
        py.Attribute(py.Name('buf', py.Load()), 'write', py.Load()),
        [value], [], None, None,
    ))


def _write_str(value):
    return _write(py.Str(value))


def _ctx_load(name):
    return py.Subscript(py.Name('ctx', py.Load()),
                        py.Index(py.Str(name)), py.Load())


def _ctx_store(name):
    return py.Subscript(py.Name('ctx', py.Load()),
                        py.Index(py.Str(name)), py.Store())


def _buf_push():
    return py.Expr(py.Call(
        py.Attribute(py.Name('buf', py.Load()), 'push', py.Load()),
        [], [], None, None,
    ))


def _buf_pop():
    return py.Call(py.Attribute(py.Name('buf', py.Load()),
                                'pop', py.Load()),
                   [], [], None, None)


def _yield_writes(env, node):
    if returns_markup(node):
        for item in compile_stmt(env, node):
            yield item
    else:
        yield _write(compile_expr(env, node))


class _PlaceholdersExtractor(NodeVisitor):

    def __init__(self):
        # using list to preserve placeholders order for the tests
        self.placeholders = []

    def visit_placeholder(self, node):
        if node.name not in self.placeholders:
            self.placeholders.append(node.name)


def _cls_eq(i, name):
    return i.__class__.__name__ == name


def _node_copy(func):
    def wrapper(self, node):
        node = self.generic_visit(node)
        node_cls = type(node)
        new_node = node_cls(*[value for _, value in iter_fields(node)])
        copy_location(new_node, node)
        func(self, new_node)
        return new_node
    return wrapper


class _Optimizer(NodeTransformer):

    def _paste(self, body):
        chunks = []
        for item in body:
            if (
                _cls_eq(item, 'Expr') and
                _cls_eq(item.value, 'Call') and
                _cls_eq(item.value.func, 'Attribute') and
                _cls_eq(item.value.func.value, 'Name') and
                item.value.func.value.id == 'buf' and
                item.value.func.attr == 'write' and
                len(item.value.args) == 1 and
                (_cls_eq(item.value.args[0], 'Str') or
                 _cls_eq(item.value.args[0], 'Num'))
            ):
                if _cls_eq(item.value.args[0], 'Str'):
                    chunks.append(item.value.args[0].s)
                else:
                    chunks.append(text_type(item.value.args[0].n))
            else:
                if chunks:
                    yield _write_str(u''.join(chunks))
                    del chunks[:]
                yield item
        if chunks:
            yield _write_str(u''.join(chunks))

    @_node_copy
    def visit_Module(self, node):
        node.body = list(self._paste(node.body))

    @_node_copy
    def visit_FunctionDef(self, node):
        node.body = list(self._paste(node.body))

    @_node_copy
    def visit_If(self, node):
        node.body = list(self._paste(node.body))
        node.orelse = list(self._paste(node.orelse))

    @_node_copy
    def visit_For(self, node):
        node.body = list(self._paste(node.body))


def compile_if1_expr(env, node, test, then_):
    test_expr = compile_expr(env, test)
    then_expr = compile_expr(env, then_)
    else_expr = py.Name('None', py.Load())
    return py.IfExp(test_expr, then_expr, else_expr)


def compile_if2_expr(env, node, test, then_, else_):
    test_expr = compile_expr(env, test)
    then_expr = compile_expr(env, then_)
    else_expr = compile_expr(env, else_)
    return py.IfExp(test_expr, then_expr, else_expr)


def compile_get_expr(env, node, obj, attr):
    obj_expr = compile_expr(env, obj)
    return py.Subscript(obj_expr, py.Index(py.Str(attr.name)), py.Load())


def compile_func_expr(env, node, *norm_args):
    sym, args = node.values[0], node.values[1:]
    pos_args, kw_args = split_args(args)

    name_expr = py.Attribute(py.Name('builtins', py.Load()),
                             sym.name, py.Load())

    pos_arg_exprs = []
    for value in pos_args:
        pos_arg_exprs.append(compile_expr(env, value))

    kw_arg_exprs = []
    for key, value in kw_args.items():
        kw_arg_exprs.append(py.keyword(key, compile_expr(env, value)))

    return py.Call(name_expr, pos_arg_exprs, kw_arg_exprs, None, None)


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
            return py.Name(env[node.name], py.Load())
        else:
            return _ctx_load(node.name)

    elif isinstance(node, Placeholder):
        return py.Name(env[node.name], py.Load())

    elif isinstance(node, String):
        return py.Str(node.value)

    elif isinstance(node, Number):
        return py.Num(node.value)

    else:
        raise TypeError('Unable to compile {!r} of type {!r} as expression'
                        .format(node, type(node)))


def compile_def_stmt(env, node, name_sym, body):
    arg_names = [a.__arg_name__ for a in get_type(node).__args__]
    with env.push(['buf', 'ctx']):
        py_args = [py.arg('buf'), py.arg('ctx')]
        with env.push(arg_names):
            py_args.extend(py.arg(env[arg]) for arg in arg_names)
            yield py.FunctionDef(name_sym.name,
                                 py.arguments(py_args, None, None, []),
                                 list(compile_stmts(env, body)), [])


def compile_html_tag_stmt(env, node, attrs, body):
    tag_name = node.values[0].name
    yield _write_str(u'<{}'.format(tag_name))
    for key, value in attrs.items():
        yield _write_str(u' {}="'.format(key))
        yield _write(compile_expr(env, value))
        yield _write_str(u'"')
    if tag_name in SELF_CLOSING_ELEMENTS:
        yield _write_str(u'/>')
        assert not body, ('Positional args are not expected in the '
                          'self-closing elements')
        return
    else:
        yield _write_str(u'>')
    for arg in body:
        for item in _yield_writes(env, arg):
            yield item
    yield _write_str(u'</{}>'.format(tag_name))


def compile_if1_stmt(env, node, test, then_):
    test_expr = compile_expr(env, test)
    yield py.If(test_expr, list(_yield_writes(env, then_)), [])


def compile_if2_stmt(env, node, test, then_, else_):
    test_expr = compile_expr(env, test)
    yield py.If(test_expr, list(_yield_writes(env, then_)),
                list(_yield_writes(env, else_)))


def compile_each_stmt(env, node, var, col, body):
    with env.push([var.name]):
        yield py.For(py.Name(env[var.name], py.Store()), compile_expr(env, col),
                     list(compile_stmts(env, body)), [])


def compile_join1_stmt(env, node, col):
    for value in col.values:
        for item in _yield_writes(env, value):
            yield item


def compile_join2_stmt(env, node, sep, col):
    for i, value in enumerate(col.values):
        if i:
            yield _write_str(sep.value)
        for item in _yield_writes(env, value):
            yield item


def compile_get_stmt(env, node, obj, attr):
    obj_expr = compile_expr(env, obj)
    yield _write(py.Subscript(obj_expr, py.Index(py.Str(attr.name)), py.Load()))


STMT_TYPES = {
    DEF_TYPE: compile_def_stmt,
    HTML_TAG_TYPE: compile_html_tag_stmt,
    IF1_TYPE: compile_if1_stmt,
    IF2_TYPE: compile_if2_stmt,
    EACH_TYPE: compile_each_stmt,
    JOIN1_TYPE: compile_join1_stmt,
    JOIN2_TYPE: compile_join2_stmt,
    GET_TYPE: compile_get_stmt,
}


def compile_func_stmt(env, node, *norm_args):
    sym = node.values[0]

    pos_args, kw_args = [], {}
    for arg_type, arg_value in zip(sym.__type__.__args__, norm_args):
        if isinstance(arg_type, NamedArgMeta):
            kw_args[arg_type.__arg_name__] = (arg_type.__arg_type__, arg_value)
        elif isinstance(arg_type, VarArgsMeta):
            pos_args.extend((arg_type.__arg_type__, v) for v in arg_value)
        elif isinstance(arg_type, VarNamedArgsMeta):
            kw_args.update({key: (arg_type.__arg_type__, value)
                            for key, value in arg_value.items()})
        else:
            pos_args.append((arg_type, arg_value))

    if sym.ns:
        if sym.ns == '.':
            name_expr = py.Name(sym.rel, py.Load())
        else:
            name_expr = py.Name('.'.join([sym.ns, sym.rel]), py.Load())
    else:
        name_expr = py.Attribute(py.Name('builtins', py.Load()),
                                 sym.name, py.Load())

    kw_arg_exprs = []
    for key, (type_, value) in kw_args.items():
        if returns_markup(value):
            yield _buf_push()
            for item in _yield_writes(env, value):
                yield item
            kw_arg_exprs.append(py.keyword(key, _buf_pop()))
        else:
            kw_arg_exprs.append(py.keyword(key, compile_expr(env, value)))

    pos_arg_exprs = []
    # capturing args in reversed order to preserve proper ordering
    # during second reverse
    for type_, value in reversed(pos_args):
        if returns_markup(value):
            yield _buf_push()
            for item in _yield_writes(env, value):
                yield item
            pos_arg_exprs.append(_buf_pop())
        else:
            pos_arg_exprs.append(compile_expr(env, value))

    pos_arg_exprs.extend([py.Name('ctx', py.Load()),
                          py.Name('buf', py.Load())])

    # applying args in reversed order to preserve pushes/pops
    # consistency
    py_call = py.Call(name_expr,
                      pos_arg_exprs[::-1],
                      kw_arg_exprs[::-1],
                      None, None)
    yield (py.Expr(py_call) if sym.ns else py_call)


def compile_stmt(env, node):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        assert sym.__type__

        pos_args, kw_args = split_args(args)
        norm_args = normalize_args(sym.__type__, pos_args, kw_args)

        proc = STMT_TYPES.get(sym.__type__, compile_func_stmt)
        for item in proc(env, node, *norm_args):
            yield item

    elif isinstance(node, Symbol):
        if node.name in env:
            yield _write(py.Name(env[node.name], py.Load()))
        else:
            yield _write(_ctx_load(node.name))

    elif isinstance(node, Placeholder):
        yield _write(py.Name(env[node.name], py.Load()))

    elif isinstance(node, String):
        yield _write(py.Str(node.value))

    elif isinstance(node, Number):
        yield _write(py.Num(node.value))

    else:
        raise TypeError('Unable to compile {!r} of type {!r} as statement'
                        .format(node, type(node)))


def compile_stmts(env, nodes):
    for node in nodes:
        for item in compile_stmt(env, node):
            yield item


def compile_module(body):
    assert isinstance(body, List), repr(body)
    env = Environ()
    mod = py.Module(list(compile_stmts(env, body.values)))
    mod = _Optimizer().visit(mod)
    fix_missing_locations(mod)
    return mod


def dumps(node):
    return astor.to_source(node) + '\n'
