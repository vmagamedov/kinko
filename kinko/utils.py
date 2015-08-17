import io

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
