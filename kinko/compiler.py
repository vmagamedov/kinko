from __future__ import absolute_import
import sys

try:
    from functools import singledispatch
except ImportError:
    from singledispatch import singledispatch

import ast as P

import astor

from . import ast as A


if sys.version_info >= (3, 0):

    def arguments(args):
        return P.arguments([P.Name("buf", False)], None, [], [], None, [])

    def mkfunc(name, args, body):
        return P.FunctionDef(name, args, body, [], None)

else:

    def arguments(args):
        return P.arguments([P.Name("buf", False)], None, None, [])

    def mkfunc(name, args, body):
        return P.FunctionDef(name, args, body, [])


@singledispatch
def expr(node):
    """Expression visitor"""
    raise NotImplementedError(node)


@singledispatch
def writer(node):
    """Statement visitor (i.e. function body toplevel element)

    Note it should return expression anyway, because it should work in labmdas
    """
    return buf_write(expr(node))


@expr.register(A.String)
def expr_string(node):
    return P.Str(node.value)


@writer.register(A.String)
def writer_string(node):
    return buf_write(P.Str(node.value))

@expr.register(A.Attr)
def expr_attr(node):
    return P.Attribute(expr(node.expr), node.attr, True)


def buf_write(expr):
    return P.Call(P.Attribute(P.Name('buf', True), 'write', True),
                         # TODO(tailhook) html escape
                         [expr], [], None, None)

@expr.register(A.Name)
def expr_name(node):
    # TODO(Tailhook) possibly rename variable
    return P.Name(node.name, True)


@expr.register(A.Attr)
def expr_attr(node):
    return P.Attribute(expr(node.expr), node.attr, True)


def process_function(func):
    assert not func.arguments # TODO(tailhook)
    return mkfunc(func.name,
        arguments(["buf"]),
        list(map(P.Expr, map(writer, func.body))))


@expr.register(A.GenericCall)
@writer.register(A.GenericCall)
def build_generic_call(func):
    args = [P.Lambda(arguments(['buf']), writer(x)) for x in func.args]
    return P.Call(P.Name(func.name, True),
                  [P.Name("buf", True)] + args, [], None, None)


def compile_module(ast):
    body = list(map(process_function, ast.functions))
    return P.Module(body=body)


def compile_to_string(ast):
    return astor.to_source(compile_module(ast))
