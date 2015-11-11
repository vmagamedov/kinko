import io

from .nodes import Keyword
from .types import TypeVar
from .compat import texttype


class Buffer(object):

    def __init__(self):
        self.stack = []

    def write(self, s):
        self.stack[-1].write(texttype(s))

    def push(self):
        self.stack.append(io.StringIO())

    def pop(self):
        return self.stack.pop().getvalue()


class VarsGen(object):

    def __init__(self):
        self.vars = {}

    def __getattr__(self, name):
        if name not in self.vars:
            self.vars[name] = TypeVar[None]
        return self.vars[name]


def split_args(args):
    _pos_args, _kw_args = [], {}
    i = iter(args)
    try:
        while True:
            arg = next(i)
            if isinstance(arg, Keyword):
                try:
                    val = next(i)
                except StopIteration:
                    raise TypeError('Missing named argument value')
                else:
                    _kw_args[arg.name] = val
            else:
                _pos_args.append(arg)
    except StopIteration:
        return _pos_args, _kw_args
