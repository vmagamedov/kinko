from __future__ import absolute_import

try:
    from functools import singledispatch
except ImportError:
    from singledispatch import singledispatch

import ast as P

import astor

from . import ast as A


@singledispatch
def build(node):
    raise NotImplementedError(node)


@build.register(A.Function)
def build_function(func):
    assert not func.arguments # TODO(tailhook)
    return P.FunctionDef(func.name,
        P.arguments([P.Name("buf", False)], None, None, []),
        list(map(build, func.body)),
        [])


@build.register(A.GenericCall)
def build_generic_call(func):
    return P.Call(P.Name(func.name, True),
                  [P.Name("buf", True)], [], None, None)


@build.register(A.File)
def build_file(file):
    # TODO(tailhook) add imports
    body = list(map(build, file.functions))
    return P.Module(body=body)


def compile_to_string(ast):
    body = build(ast)
    return astor.to_source(body)
