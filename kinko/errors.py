from contextlib import contextmanager
from collections import namedtuple

from .compat import text_type


Error = namedtuple('Error', ['module', 'location', 'message'])


class UserError(Exception):
    pass


class Errors(object):
    module = None

    def __init__(self):
        self.list = []

    @contextmanager
    def location(self, location):
        try:
            yield
        except UserError as e:
            self.report(location, text_type(e))
            raise

    def report(self, location, message):
        self.list.append(Error(self.module, location, message))
