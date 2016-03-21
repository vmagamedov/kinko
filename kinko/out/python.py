from __future__ import absolute_import, unicode_literals

from ast import NodeTransformer, iter_fields, copy_location
from ast import fix_missing_locations

import astor

from .. import compat_ast as py
from ..types import NamedArgMeta, VarArgsMeta, VarNamedArgsMeta, UnionMeta
from ..types import StringTypeMeta
from ..nodes import String, Tuple, Symbol, List, Number, Placeholder
from ..nodes import NodeVisitor
from ..utils import Environ
from ..compat import text_type, text_type_name
from ..checker import split_args, normalize_args, DEF_TYPE, HTML_TAG_TYPE
from ..checker import IF1_TYPE, IF2_TYPE, EACH_TYPE, JOIN1_TYPE, JOIN2_TYPE
from ..checker import GET_TYPE, get_type, returns_markup, IF3_TYPE
from ..checker import IF_SOME1_TYPE, IF_SOME2_TYPE, IF_SOME3_TYPE, LET_TYPE
from ..constant import SELF_CLOSING_ELEMENTS


def _contains_string(type_):
    def recur_check(t):
        if isinstance(t, UnionMeta):
            return any(recur_check(st) for st in t.__types__)
        else:
            return isinstance(t, StringTypeMeta)
    return recur_check(type_)


def _write(value, node=None):
    safe = isinstance(value, py.Str)
    if not safe and node is not None:
        safe = not _contains_string(get_type(node))
    write_method = 'write' if safe else 'write_unsafe'
    buffer = py.Attribute(py.Name('ctx', py.Load()), 'buffer', py.Load())
    return py.Expr(py.Call(py.Attribute(buffer, write_method, py.Load()),
                           [value], [], None, None))


def _write_str(value):
    return _write(py.Str(value))


def _result_get(name):
    result = py.Attribute(py.Name('ctx', py.Load()), 'result', py.Load())
    return py.Subscript(result, py.Index(py.Str(name)), py.Load())


def _buf_push():
    buffer = py.Attribute(py.Name('ctx', py.Load()), 'buffer', py.Load())
    return py.Expr(py.Call(py.Attribute(buffer, 'push', py.Load()),
                           [], [], None, None))


def _buf_pop():
    buffer = py.Attribute(py.Name('ctx', py.Load()), 'buffer', py.Load())
    return py.Call(py.Attribute(buffer, 'pop', py.Load()),
                   [], [], None, None)


def _yield_writes(env, node):
    if returns_markup(node):
        for item in compile_stmt(env, node):
            yield item
    else:
        yield _write(compile_expr(env, node), node)


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


def _maybe_write(node):
    if not _cls_eq(node, 'Expr') or not _cls_eq(node.value, 'Call'):
        return
    callable_ = node.value.func

    if not _cls_eq(callable_, 'Attribute') or not callable_.attr == 'write':
        return
    has_write = callable_.value

    if not _cls_eq(has_write, 'Attribute') or not has_write.attr == 'buffer':
        return
    has_buffer = has_write.value

    if not _cls_eq(has_buffer, 'Name') or not has_buffer.id == 'ctx':
        return
    if len(node.value.args) == 1:
        if _cls_eq(node.value.args[0], 'Str'):
            return node.value.args[0].s
        elif _cls_eq(node.value.args[0], 'Num'):
            return text_type(node.value.args[0].n)


class _Optimizer(NodeTransformer):

    def _paste(self, body):
        chunks = []
        for item in body:
            chunk = _maybe_write(item)
            if chunk is not None:
                chunks.append(chunk)
            else:
                if chunks:
                    yield _write_str(''.join(chunks))
                    del chunks[:]
                yield item
        if chunks:
            yield _write_str(''.join(chunks))

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


def _let_expr(env, bindings, expr_compiler):
    names, values = bindings.values[::2], bindings.values[1::2]
    value_exprs = [compile_expr(env, value) for value in values]
    with env.push([sym.name for sym in names]):
        vars_ = py.Tuple([py.Name(env[sym.name], py.Store()) for sym in names],
                         py.Store())
        list_comp = py.ListComp(
            expr_compiler(),
            [py.comprehension(vars_, py.List([py.Tuple(value_exprs, py.Load())],
                                             py.Load()), [])],
        )
        return py.Subscript(list_comp, py.Index(py.Num(0)), py.Load())


def compile_let_expr(env, node, bindings, expr):
    return _let_expr(env, bindings, lambda: compile_expr(env, expr))


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


def compile_if_some1_expr(env, node, bind, then_):
    sym, _ = bind.values

    def compiler():
        test_expr = py.Compare(py.Name(env[sym.name], py.Load()),
                               [py.IsNot()], [py.Name('None', py.Load())])
        then_expr = compile_expr(env, then_)
        return py.IfExp(test_expr, then_expr, py.Name('None', py.Load()))

    return _let_expr(env, bind, compiler)


def compile_if_some2_expr(env, node, bind, then_, else_):
    sym, _ = bind.values

    def compiler():
        test_expr = py.Compare(py.Name(env[sym.name], py.Load()),
                               [py.IsNot()], [py.Name('None', py.Load())])
        then_expr = compile_expr(env, then_)
        else_expr = compile_expr(env, else_)
        return py.IfExp(test_expr, then_expr, else_expr)

    return _let_expr(env, bind, compiler)


def compile_join2_expr(env, node, sep, values):
    sep_expr = compile_expr(env, sep)
    values_expr = compile_expr(env, values)
    join = py.Attribute(sep_expr, 'join', py.Load())
    with env.push(['_i']):
        values_gen = py.GeneratorExp(
            py.Call(py.Name(text_type_name, py.Load()),
                    [py.Name(env['_i'], py.Load())], [], None, None),
            [py.comprehension(py.Name(env['_i'], py.Store()),
                              values_expr, [])],
        )
    return py.Call(join, [values_gen], [], None, None)


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
    LET_TYPE: compile_let_expr,
    IF1_TYPE: compile_if1_expr,
    IF2_TYPE: compile_if2_expr,
    IF3_TYPE: compile_if2_expr,
    IF_SOME1_TYPE: compile_if_some1_expr,
    IF_SOME2_TYPE: compile_if_some2_expr,
    IF_SOME3_TYPE: compile_if_some2_expr,
    JOIN2_TYPE: compile_join2_expr,
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
            return _result_get(node.name)

    elif isinstance(node, Placeholder):
        return py.Name(env[node.name], py.Load())

    elif isinstance(node, String):
        return py.Str(node.value)

    elif isinstance(node, Number):
        return py.Num(node.value)

    elif isinstance(node, List):
        return py.List([compile_expr(env, e) for e in node.values], py.Load())

    else:
        raise TypeError('Unable to compile {!r} of type {!r} as expression'
                        .format(node, type(node)))


def compile_def_stmt(env, node, name_sym, body):
    arg_names = [a.__arg_name__ for a in get_type(node).__args__]
    with env.push(['ctx']):
        py_args = [py.arg('ctx')]
        with env.push(arg_names):
            py_args.extend(py.arg(env[arg]) for arg in arg_names)
            yield py.FunctionDef(name_sym.name,
                                 py.arguments(py_args, None, None, []),
                                 list(compile_stmt(env, body)), [])


def compile_let_stmt(env, node, bindings, expr):
    names, values = bindings.values[::2], bindings.values[1::2]
    value_exprs = [compile_expr(env, value) for value in values]
    with env.push([sym.name for sym in names]):
        for sym, value_expr in zip(names, value_exprs):
            yield py.Assign([py.Name(env[sym.name], py.Store())], value_expr)
        for item in _yield_writes(env, expr):
            yield item


def compile_html_tag_stmt(env, node, attrs, body):
    tag_name = node.values[0].name
    yield _write_str('<{}'.format(tag_name))
    for key, value in attrs.items():
        yield _write_str(' {}="'.format(key))
        yield _write(compile_expr(env, value), value)
        yield _write_str('"')
    if tag_name in SELF_CLOSING_ELEMENTS:
        yield _write_str('/>')
        assert not body, ('Positional args are not expected in the '
                          'self-closing elements')
        return
    else:
        yield _write_str('>')
    for arg in body:
        for item in _yield_writes(env, arg):
            yield item
    yield _write_str('</{}>'.format(tag_name))


def compile_if1_stmt(env, node, test, then_):
    test_expr = compile_expr(env, test)
    yield py.If(test_expr, list(_yield_writes(env, then_)), [])


def compile_if2_stmt(env, node, test, then_, else_):
    test_expr = compile_expr(env, test)
    yield py.If(test_expr, list(_yield_writes(env, then_)),
                list(_yield_writes(env, else_)))


def compile_if_some1_stmt(env, node, bind, then_):
    sym, value = bind.values
    value_expr = compile_expr(env, value)
    with env.push([sym.name]):
        yield py.Assign([py.Name(env[sym.name], py.Store())], value_expr)
        test_expr = py.Compare(py.Name(env[sym.name], py.Load()),
                               [py.IsNot()], [py.Name('None', py.Load())])
        yield py.If(test_expr, list(_yield_writes(env, then_)), [])


def compile_if_some2_stmt(env, node, bind, then_, else_):
    sym, value = bind.values
    value_expr = compile_expr(env, value)
    with env.push([sym.name]):
        yield py.Assign([py.Name(env[sym.name], py.Store())], value_expr)
        test_expr = py.Compare(py.Name(env[sym.name], py.Load()),
                               [py.IsNot()], [py.Name('None', py.Load())])
        yield py.If(test_expr,
                    list(_yield_writes(env, then_)),
                    list(_yield_writes(env, else_)))


def compile_each_stmt(env, node, var, col, body):
    with env.push([var.name]):
        yield py.For(py.Name(env[var.name], py.Store()), compile_expr(env, col),
                     list(compile_stmt(env, body)), [])


def compile_join1_stmt(env, node, col):
    for value in col.values:
        for item in _yield_writes(env, value):
            yield item


def compile_get_stmt(env, node, obj, attr):
    obj_expr = compile_expr(env, obj)
    yield _write(py.Subscript(obj_expr, py.Index(py.Str(attr.name)),
                              py.Load()), node)


STMT_TYPES = {
    DEF_TYPE: compile_def_stmt,
    LET_TYPE: compile_let_stmt,
    HTML_TAG_TYPE: compile_html_tag_stmt,
    IF1_TYPE: compile_if1_stmt,
    IF2_TYPE: compile_if2_stmt,
    IF3_TYPE: compile_if2_stmt,
    IF_SOME1_TYPE: compile_if_some1_stmt,
    IF_SOME2_TYPE: compile_if_some2_stmt,
    IF_SOME3_TYPE: compile_if_some2_stmt,
    EACH_TYPE: compile_each_stmt,
    JOIN1_TYPE: compile_join1_stmt,
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
            name_expr = py.Call(py.Attribute(py.Name('ctx', py.Load()),
                                             'lookup', py.Load()),
                                [py.Str(sym.name)], [], None, None)
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

    pos_arg_exprs.extend([py.Name('ctx', py.Load())])

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
            yield _write(py.Name(env[node.name], py.Load()), node)
        else:
            yield _write(_result_get(node.name), node)

    elif isinstance(node, Placeholder):
        yield _write(py.Name(env[node.name], py.Load()), node)

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
