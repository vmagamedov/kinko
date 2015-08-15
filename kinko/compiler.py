from itertools import chain

import astor

from kinko.nodes import String, Tuple, Symbol, List, Number, Placeholder
from kinko.nodes import NodeVisitor
from kinko.compat import ast as py
from kinko.checker import split_args
from kinko.constant import HTML_ELEMENTS, SELF_CLOSING_ELEMENTS


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
        for item in compile_(node, True):
            yield item
    else:
        for item in compile_(node, True):
            yield _write(item)


class _PlaceholdersExtractor(NodeVisitor):

    def __init__(self):
        # using list to preserve placeholders order for the tests
        self.placeholders = []

    def visit_placeholder(self, node):
        if node.name not in self.placeholders:
            self.placeholders.append(node.name)


def compile_(node, as_statement):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        pos_args, kw_args = split_args(args)
        if sym.name == 'def':
            assert as_statement
            name_sym, body = pos_args
            visitor = _PlaceholdersExtractor()
            visitor.visit(body)
            py_args = [py.arg(p) for p in visitor.placeholders]
            yield py.FunctionDef(name_sym.name,
                                 py.arguments(py_args, None, None, []),
                                 list(compile_(body, as_statement)), [])

        elif sym.name in HTML_ELEMENTS:
            assert as_statement
            yield _write_str('<{}'.format(sym.name))
            for key, value in kw_args.items():
                yield _write_str(' {}="'.format(key))
                for item in _yield_writes(value):
                    yield item
                yield _write_str('"')
            if sym.name in SELF_CLOSING_ELEMENTS:
                yield _write_str('/>')
                assert not pos_args, ('Positional args are not expected in the '
                                      'self-closing elements')
                return
            else:
                yield _write_str('>')
            for arg in pos_args:
                for item in _yield_writes(arg):
                    yield item
            yield _write_str('</{}>'.format(sym.name))

        elif sym.name == 'if':
            if kw_args:
                test, = pos_args
                then_, else_ = kw_args['then'], kw_args.get('else')
            elif len(pos_args) == 3:
                test, then_, else_ = pos_args
            else:
                (test, then_), else_ = pos_args, None

            test_expr = compile_expr(test)

            if as_statement:
                then_stmt = list(_yield_writes(then_))
                else_stmt = list(_yield_writes(else_)) if else_ is not None \
                    else []
                yield py.If(test_expr, then_stmt, else_stmt)
            else:
                then_expr = compile_expr(then_)
                # FIXME: implement custom none/null type or require "else"
                # expression like in Python
                else_expr = compile_expr(else_) if else_ is not None \
                    else py.Name('None', py.Load())
                yield py.IfExp(test_expr, then_expr, else_expr)

        elif sym.name == 'each':
            assert as_statement
            var, col, body = pos_args
            yield py.For(_ctx_store(var.name), _ctx_load(col.name),
                         list(compile_(body, as_statement)), [])

        elif sym.name == 'join':
            assert as_statement
            if len(pos_args) == 1:
                separator, (collection,) = None, pos_args
            else:
                separator, collection = pos_args
            for i, value in enumerate(collection.values):
                if i and separator is not None:
                    yield _write_str(separator.value)
                for item in _yield_writes(value):
                    yield item

        elif sym.name == 'get':
            obj, attr = pos_args
            obj_expr = compile_expr(obj)
            yield py.Attribute(obj_expr, attr.name, py.Load())

        else:
            if sym.ns:
                if sym.ns == '.':
                    name_expr = py.Name(sym.rel, py.Load())
                else:
                    name_expr = py.Name('.'.join([sym.ns, sym.rel]), py.Load())
            else:
                name_expr = py.Attribute(py.Name('builtins', py.Load()),
                                         sym.name, py.Load())

            kw_arg_exprs = []
            for key, value in kw_args.items():
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
            for value in reversed(pos_args):
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

    elif isinstance(node, Symbol):
        yield _ctx_load(node.name)

    elif isinstance(node, Placeholder):
        yield py.Name(node.name, py.Load())

    elif isinstance(node, String):
        yield py.Str(node.value)

    elif isinstance(node, Number):
        yield py.Num(node.value)

    else:
        raise TypeError('Unable to compile {!r} of type {!r}'
                        .format(node, type(node)))


def compile_expr(node):
    compiled, = list(compile_(node, False))
    return compiled


def compile_module(body):
    assert isinstance(body, List), repr(body)
    mod = py.Module(list(chain.from_iterable(
        compile_(n, True) for n in body.values
    )))
    py.fix_missing_locations(mod)
    return mod


def dumps(node):
    return astor.to_source(node)
