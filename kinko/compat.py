import sys
import ast as _ast


PY3 = sys.version_info[0] == 3


def with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""
    # This requires a bit of explanation: the basic idea is to make a dummy
    # metaclass for one level of class instantiation that replaces itself with
    # the actual metaclass.
    class metaclass(meta):

        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)
    return type.__new__(metaclass, 'temporary_class', (), {})


class _AST(object):

    def __getattr__(self, name):
        return getattr(_ast, name)

    @staticmethod
    def arguments(args, vararg, kwarg, defaults):
        if PY3:
            return _ast.arguments(args, vararg, None, [], kwarg, defaults)
        else:
            return _ast.arguments(args, vararg, kwarg, defaults)

    @staticmethod
    def FunctionDef(name, args, body, decorator_list):
        if PY3:
            return _ast.FunctionDef(name, args, body, decorator_list, None)
        else:
            return _ast.FunctionDef(name, args, body, decorator_list)


ast = _AST()
