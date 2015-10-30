from ast import NodeTransformer, iter_fields, copy_location
from itertools import chain

import astor

from .types import NamedArgMeta, VarArgsMeta, VarNamedArgsMeta
from .nodes import String, Tuple, Symbol, List, Number, Placeholder
from .nodes import NodeVisitor
from .compat import ast as py, texttype
from .checker import split_args, normalize_args, DEF_TYPE, HTML_TAG_TYPE
from .checker import IF1_TYPE, IF2_TYPE, EACH_TYPE, JOIN1_TYPE, JOIN2_TYPE
from .checker import GET_TYPE
from .constant import HTML_ELEMENTS, SELF_CLOSING_ELEMENTS


def _write(value):
    return py.Expr(py.Call(
        py.Attribute(py.Name('buf', py.Load()), 'write', py.Load()),
        [value], [], None, None,
    ))


def _write_str(value):
    return _write(py.Str(value))


def _ctx_load(name):
    return py.Attribute(py.Name('ctx', py.Load()), name, py.Load())


def _ctx_store(name):
    return py.Attribute(py.Name('ctx', py.Load()), name, py.Store())


def _buf_push():
    return py.Expr(py.Call(
        py.Attribute(py.Name('buf', py.Load()), 'push', py.Load()),
        [], [], None, None,
    ))


def _buf_pop():
    return py.Call(py.Attribute(py.Name('buf', py.Load()),
                                'pop', py.Load()),
                   [], [], None, None)


def _returns_output_type(node):
    # FIXME: temporary hack before we will have working types system
    return (
        isinstance(node, Tuple) and
        (node.values[0].name in {'each', 'if', 'join'} or
         node.values[0].name in HTML_ELEMENTS or
         node.values[0].ns)
    )


def _yield_writes(node):
    if _returns_output_type(node):
        for item in compile_stmt(node):
            yield item
    else:
        for item in compile_stmt(node):
            yield _write(item)


class _PlaceholdersExtractor(NodeVisitor):

    def __init__(self):
        # using list to preserve placeholders order for the tests
        self.placeholders = []

    def visit_placeholder(self, node):
        if node.name not in self.placeholders:
            self.placeholders.append(node.name)


_cls_eq = lambda i, name: i.__class__.__name__ == name


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
                    chunks.append(texttype(item.value.args[0].n))
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


def compile_if1_expr(node, test, then_):
    test_expr = compile_expr(test)
    then_expr = compile_expr(then_)
    else_expr = py.Name('None', py.Load())
    return py.IfExp(test_expr, then_expr, else_expr)


def compile_if2_expr(node, test, then_, else_):
    test_expr = compile_expr(test)
    then_expr = compile_expr(then_)
    else_expr = compile_expr(else_)
    return py.IfExp(test_expr, then_expr, else_expr)


def compile_get_expr(node, obj, attr):
    obj_expr = compile_expr(obj)
    return py.Attribute(obj_expr, attr.name, py.Load())


EXPR_TYPES = {
    IF1_TYPE: compile_if1_expr,
    IF2_TYPE: compile_if2_expr,
    GET_TYPE: compile_get_expr,
}


def compile_expr(node):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        assert sym.__type__
        pos_args, kw_args = split_args(args)
        norm_args = normalize_args(sym.__type__, pos_args, kw_args)
        proc = EXPR_TYPES[sym.__type__]
        return proc(node, *norm_args)

    elif isinstance(node, Symbol):
        return _ctx_load(node.name)

    elif isinstance(node, Placeholder):
        return py.Name(node.name, py.Load())

    elif isinstance(node, String):
        return py.Str(node.value)

    elif isinstance(node, Number):
        return py.Num(node.value)

    else:
        raise TypeError('Unable to compile {!r} of type {!r} as expression'
                        .format(node, type(node)))


def _chain_map(fn, iterable):
    return list(chain.from_iterable(map(fn, iterable)))


def compile_def_stmt(node, name_sym, body):
    py_args = [py.arg(a.__arg_name__)
               for a in node.__type__.__instance__.__args__]
    yield py.FunctionDef(name_sym.name,
                         py.arguments(py_args, None, None, []),
                         _chain_map(compile_stmt, body), [])


def compile_html_tag_stmt(node, attrs, body):
    tag_name = node.values[0].name
    yield _write_str(u'<{}'.format(tag_name))
    for key, value in attrs.items():
        yield _write_str(u' {}="'.format(key))
        for item in _yield_writes(value):
            yield item
        yield _write_str(u'"')
    if tag_name in SELF_CLOSING_ELEMENTS:
        yield _write_str(u'/>')
        assert not body, ('Positional args are not expected in the '
                          'self-closing elements')
        return
    else:
        yield _write_str(u'>')
    for arg in body:
        for item in _yield_writes(arg):
            yield item
    yield _write_str(u'</{}>'.format(tag_name))


def compile_if1_stmt(node, test, then_):
    test_expr = compile_expr(test)
    yield py.If(test_expr, list(_yield_writes(then_)), [])


def compile_if2_stmt(node, test, then_, else_):
    test_expr = compile_expr(test)
    yield py.If(test_expr, list(_yield_writes(then_)), list(_yield_writes(else_)))


def compile_each_stmt(node, var, col, body):
    yield py.For(_ctx_store(var.name), _ctx_load(col.name),
                 _chain_map(compile_stmt, body), [])


def compile_join1_stmt(node, col):
    for value in col.values:
        for item in _yield_writes(value):
            yield item


def compile_join2_stmt(node, sep, col):
    for i, value in enumerate(col.values):
        if i:
            yield _write_str(sep.value)
        for item in _yield_writes(value):
            yield item


def compile_get_stmt(node, obj, attr):
    obj_expr = compile_expr(obj)
    yield py.Attribute(obj_expr, attr.name, py.Load())


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


def compile_func_stmt(node, *norm_args):
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
        if _returns_output_type(value):
            yield _buf_push()
            for item in _yield_writes(value):
                yield item
            kw_arg_exprs.append(py.keyword(key, _buf_pop()))
        else:
            kw_arg_exprs.append(py.keyword(key, compile_expr(value)))

    pos_arg_exprs = []
    # capturing args in reversed order to preserve proper ordering
    # during second reverse
    for type_, value in reversed(pos_args):
        if _returns_output_type(value):
            yield _buf_push()
            for item in _yield_writes(value):
                yield item
            pos_arg_exprs.append(_buf_pop())
        else:
            pos_arg_exprs.append(compile_expr(value))

    # applying args in reversed order to preserve pushes/pops
    # consistency
    py_call = py.Call(name_expr,
                      pos_arg_exprs[::-1],
                      kw_arg_exprs[::-1],
                      None, None)
    yield (py.Expr(py_call) if sym.ns else py_call)


def compile_stmt(node):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        assert sym.__type__

        pos_args, kw_args = split_args(args)
        norm_args = normalize_args(sym.__type__, pos_args, kw_args)

        proc = STMT_TYPES.get(sym.__type__, compile_func_stmt)
        for item in proc(node, *norm_args):
            yield item

    elif isinstance(node, Symbol):
        yield _ctx_load(node.name)

    elif isinstance(node, Placeholder):
        yield py.Name(node.name, py.Load())

    elif isinstance(node, String):
        yield py.Str(node.value)

    elif isinstance(node, Number):
        yield py.Num(node.value)

    else:
        raise TypeError('Unable to compile {!r} of type {!r} as statement'
                        .format(node, type(node)))


def compile_module(body):
    assert isinstance(body, List), repr(body)
    mod = py.Module(_chain_map(compile_stmt, body.values))
    mod = _Optimizer().visit(mod)
    py.fix_missing_locations(mod)
    return mod


def dumps(node):
    return astor.to_source(node)
