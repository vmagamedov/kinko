from __future__ import absolute_import

import ast as _ast

from ...compat import PY3


If = _ast.If
Str = _ast.Str
Num = _ast.Num
For = _ast.For
Expr = _ast.Expr
Call = _ast.Call
Name = _ast.Name
Load = _ast.Load
Index = _ast.Index
Store = _ast.Store
IfExp = _ast.IfExp
Module = _ast.Module
Subscript = _ast.Subscript


if PY3:
    def arg(arg):
        return _ast.arg(arg, None)

    def arguments(args, vararg, kwarg, defaults):
        return _ast.arguments(args, vararg, [], [], kwarg, defaults)

    def FunctionDef(name, args, body, decorator_list):
        return _ast.FunctionDef(name, args, body, decorator_list, None)

    Name = _ast.Name
    keyword = _ast.keyword
    Attribute = _ast.Attribute

else:
    def arg(arg):
        return _ast.Name(str(arg), _ast.Param())

    def arguments(args, vararg, kwarg, defaults):
        return _ast.arguments(args, vararg, kwarg, defaults)

    def FunctionDef(name, args, body, decorator_list):
        return _ast.FunctionDef(str(name), args, body, decorator_list)

    def Name(id, ctx):
        return _ast.Name(str(id), ctx)

    def keyword(arg, value):
        return _ast.keyword(str(arg), value)

    def Attribute(value, attr, ctx):
        return _ast.Attribute(value, str(attr), ctx)
