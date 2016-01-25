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

from kinko.refs import Reference
from kinko.nodes import Node
from kinko.types import GenericMeta, TypeVarMeta

Mock = _Mock


def _ne(self, other):
    return not self.__eq__(other)


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


NODE_EQ_PATCHER = patch.multiple(Node, __eq__=_node_eq, __ne__=_ne)


def _type_eq(self, other):
    if isinstance(self, TypeVarMeta) and self.__instance__ is not None:
        return _type_eq(self.__instance__, other)
    if type(self) is not type(other):
        return False
    d1 = dict(self.__dict__)
    d1.pop('__dict__')
    d1.pop('__weakref__')
    d1.pop('__backref__', None)
    d2 = dict(other.__dict__)
    d2.pop('__dict__')
    d2.pop('__weakref__')
    d2.pop('__backref__', None)
    return d1 == d2


TYPE_EQ_PATCHER = patch.multiple(GenericMeta, __eq__=_type_eq, __ne__=_ne)


def _ref_eq(self, other):
    if type(self) is not type(other):
        return False
    return self.__dict__ == other.__dict__


REF_EQ_PATCHER = patch.multiple(Reference, __eq__=_ref_eq, __ne__=_ne)


class TestCase(unittest.TestCase):
    ctx = tuple()

    def run(self, result=None):
        with _nested(*self.ctx):
            return super(TestCase, self).run(result)