from contextlib import contextmanager
from collections import namedtuple

from .compat import text_type


Func = namedtuple('Func', ['module', 'name'])

Error = namedtuple('Error', ['func', 'location', 'message', 'severity'])

WARNING = 1
ERROR = 2


class UserError(Exception):
    pass


class Errors(object):

    def __init__(self):
        self.list = []
        self._stack = [None]

    @contextmanager
    def module_ctx(self, module):
        self._stack.append(Func(module, None))
        try:
            yield
        finally:
            self._stack.pop()

    @contextmanager
    def func_ctx(self, module, name):
        self._stack.append(Func(module, name))
        try:
            yield
        finally:
            self._stack.pop()

    @contextmanager
    def location(self, location):
        try:
            yield
        except UserError as e:
            self.error(location, text_type(e))
            raise

    def warn(self, location, message):
        self.list.append(Error(self._stack[-1], location, message, WARNING))

    def error(self, location, message):
        self.list.append(Error(self._stack[-1], location, message, ERROR))
