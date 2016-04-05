from contextlib import contextmanager
from collections import namedtuple

from .compat import text_type


Error = namedtuple('Error', ['module', 'location', 'message'])


class UserError(Exception):
    pass


class Errors(object):

    def __init__(self):
        self.list = []
        self._modules = [None]

    @contextmanager
    def module(self, name):
        self._modules.append(name)
        try:
            yield
        finally:
            self._modules.pop()

    @contextmanager
    def location(self, location):
        try:
            yield
        except UserError as e:
            self.report(location, text_type(e))
            raise

    def report(self, location, message):
        self.list.append(Error(self._modules[-1], location, message))
