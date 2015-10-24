import io

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
