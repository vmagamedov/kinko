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

    if PY3:
        @staticmethod
        def arguments(args, vararg, kwarg, defaults):
            return _ast.arguments(args, vararg, [], [], kwarg, defaults)

        @staticmethod
        def FunctionDef(name, args, body, decorator_list):
            return _ast.FunctionDef(name, args, body, decorator_list, None)

        @staticmethod
        def arg(arg):
            return _ast.arg(arg, None)

    else:
        @staticmethod
        def arguments(args, vararg, kwarg, defaults):
            return _ast.arguments(args, vararg, kwarg, defaults)

        @staticmethod
        def FunctionDef(name, args, body, decorator_list):
            return _ast.FunctionDef(name, args, body, decorator_list)

        @staticmethod
        def arg(arg):
            return _ast.Name(arg, _ast.Param())


ast = _AST()


if PY3:
    import builtins

    def _exec_in(source, globals_dict):
        getattr(builtins, 'exec')(source, globals_dict)

else:
    def _exec_in(source, globals_dict):
        exec('exec source in globals_dict')
