import astor

from kinko.nodes import String, Tuple, Symbol
from kinko.compat import ast as py
from kinko.checker import split_args


def _write(value):
    return py.Call(py.Attribute(py.Name('buf', True), 'write', True),
                   [value], [], None, None)


def _ctx_var(name):
    return py.Attribute(py.Name('ctx', True), name, True)


def _write_str(value):
    return _write(py.Str(value))


def _capture(node, name):
    yield py.Call(py.Attribute(py.Name('buf', True), 'push', True),
                  [], [], None, None)
    for item in compile_(node):
        yield item
    yield py.Assign([py.Name(name, True)],
                    py.Call(py.Attribute(py.Name('buf', True),
                                         'pop', True),
                            [], [], None, None))


def compile_(node):
    if isinstance(node, Tuple):
        sym, args = node.values[0], node.values[1:]
        pos_args, kw_args = split_args(args)
        if sym.name == 'def':
            name_sym, body = pos_args
            placeholders = []  # TODO: extract placeholders from body
            yield py.FunctionDef(name_sym.name,
                                 py.arguments(placeholders, None, None, []),
                                 map(py.Expr, compile_(body)),
                                 [])

        elif sym.name == 'div':
            yield _write_str('<div')
            for key, value in kw_args.items():
                yield _write_str(' {}="'.format(key))
                for item in compile_(value):
                    yield item
                yield _write_str('"')
            yield _write_str('>')
            for arg in pos_args:
                for item in compile_(arg):
                    yield item
            yield _write_str('</div>')

        elif sym.name == 'each':
            var, col, body = pos_args
            yield py.For(_ctx_var(var.name),
                         _ctx_var(col.name),
                         map(py.Expr, compile_(body)),
                         [])

        elif sym.name == 'join':
            for arg in pos_args:
                for item in compile_(arg):
                    yield item
        else:
            # generic function call
            i = 1

            pos_value_vars = []
            for value in pos_args:
                var_name = '__anon{}'.format(i)
                for item in _capture(value, var_name):
                    yield item
                pos_value_vars.append(var_name)
                i += 1

            kw_names, kw_values = zip(*kw_args.items()) if kw_args else ([], [])
            kw_value_vars = []

            for value in kw_values:
                var_name = '__anon{}'.format(i)
                for item in _capture(value, var_name):
                    yield item
                kw_value_vars.append(var_name)
                i += 1

            yield py.Call(py.Name(sym.name, True),
                          [py.Name(var, True) for var in pos_value_vars],
                          [py.keyword(key, py.Name(value, True))
                           for key, value in zip(kw_names, kw_value_vars)],
                          None, None)

    elif isinstance(node, Symbol):
        yield _write(_ctx_var(node.name))

    elif isinstance(node, String):
        yield _write_str(node.value)

    else:
        raise TypeError('Unable to compile {!r} of type {!r}'
                        .format(node, type(node)))


def dumps(ast):
    return astor.to_source(ast)
