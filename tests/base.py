import unittest

try:
    from unittest.mock import patch, Mock as _Mock
except ImportError:
    from mock import patch, Mock as _Mock

try:
    from contextlib import nested as _nested
except ImportError:
    from contextlib import contextmanager, ExitStack

    @contextmanager
    def _nested(*managers):
        with ExitStack() as stack:
            for manager in managers:
                stack.enter_context(manager)
            yield

from kinko.nodes import Node
from kinko.types import GenericMeta


Mock = _Mock


def _node_eq(self, other):
    if type(self) is not type(other):
        return False
    d1 = dict(self.__dict__)
    d1.pop('location', None)
    t1 = d1.pop('__type__', None)
    d2 = dict(other.__dict__)
    d2.pop('location', None)
    t2 = d2.pop('__type__', None)
    if d1 == d2:
        if t1 == t2:
            return True
        else:
            raise AssertionError('Types mismatch {!r} != {!r} for expression '
                                 '`{!r}`'.format(t1, t2, self))
    else:
        return False


def _node_ne(self, other):
    return not self.__eq__(other)


node_eq_patcher = patch.multiple(Node, __eq__=_node_eq, __ne__=_node_ne)


def _type_eq(self, other):
    if type(self) is not type(other):
        return False
    d1 = dict(self.__dict__)
    d1.pop('__dict__')
    d1.pop('__weakref__')
    d1.pop('__ref__', None)
    d2 = dict(other.__dict__)
    d2.pop('__dict__')
    d2.pop('__weakref__')
    d2.pop('__ref__', None)
    return d1 == d2


def _type_ne(self, other):
    return not self.__eq__(other)


type_eq_patcher = patch.multiple(GenericMeta, __eq__=_type_eq, __ne__=_type_ne)


class TestCase(unittest.TestCase):
    ctx = tuple()

    def run(self, result=None):
        with _nested(*self.ctx):
            return super(TestCase, self).run(result)
