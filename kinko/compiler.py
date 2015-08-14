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


def _capture(node, name):
    yield py.Expr(py.Call(
        py.Attribute(py.Name('buf', py.Load()), 'push', py.Load()),
        [], [], None, None,
    ))
    for item in _yield_writes(node):
        yield item
    yield py.Assign([py.Name(name, py.Store())],
                    py.Call(py.Attribute(py.Name('buf', py.Load()),
                                         'pop', py.Load()),
                            [], [], None, None))


def _yield_writes(node):
    # FIXME: temporary hack before we will have working types system
    if (isinstance(node, Tuple) and
        (node.values[0].name in {'each', 'if', 'join'} or
         node.values[0].name in HTML_ELEMENTS or
         node.values[0].ns)):
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

            test_expr, = list(compile_(test, False))

            if as_statement:
                then_stmt = list(_yield_writes(then_))
                else_stmt = list(_yield_writes(else_)) if else_ is not None \
                    else []
                yield py.If(test_expr, then_stmt, else_stmt)
            else:
                then_expr, = list(compile_(then_, False))
                # FIXME: implement custom none/null type or require "else"
                # expression like in Python
                else_expr, = list(compile_(else_, False)) if else_ is not None \
                    else (py.Name('None', py.Load()),)
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
            obj_expr, = list(compile_(obj, False))
            yield py.Attribute(obj_expr, attr.name, py.Load())

        else:
            if sym.ns == '.':
                i = 1

                pos_value_vars = []
                for value in pos_args:
                    var_name = '__anon{}'.format(i)
                    for item in _capture(value, var_name):
                        yield item
                    pos_value_vars.append(var_name)
                    i += 1

                kw_names, kw_values = \
                    zip(*kw_args.items()) if kw_args else ([], [])
                kw_value_vars = []

                for value in kw_values:
                    var_name = '__anon{}'.format(i)
                    for item in _capture(value, var_name):
                        yield item
                    kw_value_vars.append(var_name)
                    i += 1

                yield py.Expr(py.Call(
                    py.Name(sym.rel, py.Load()),
                    [py.Name(var, py.Load()) for var in pos_value_vars],
                    [py.keyword(key, py.Name(value, py.Load()))
                     for key, value in zip(kw_names, kw_value_vars)],
                    None,
                    None,
                ))
            else:
                raise NotImplementedError(sym.name)

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


def compile_module(body):
    assert isinstance(body, List), repr(body)
    mod = py.Module(list(chain.from_iterable(
        compile_(n, True) for n in body.values
    )))
    py.fix_missing_locations(mod)
    return mod


def dumps(node):
    return astor.to_source(node)
