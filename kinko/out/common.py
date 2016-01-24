from contextlib import contextmanager
from collections import Counter

from ..types import UnionMeta, MarkupMeta
from ..checker import get_type


class Environ(object):

    def __init__(self):
        self.vars = Counter()

    def __getitem__(self, key):
        i = self.vars[key]
        return '{}_{}'.format(key, i) if i > 1 else key

    def __contains__(self, key):
        return key in self.vars

    @contextmanager
    def push(self, names):
        for name in names:
            self.vars[name] += 1
        try:
            yield
        finally:
            for name in names:
                self.vars[name] -= 1


def returns_markup(node):
    type_ = get_type(node)

    def recur_check(t):
        if isinstance(t, UnionMeta):
            return any(recur_check(st) for st in t.__types__)
        else:
            return isinstance(t, MarkupMeta)

    return recur_check(type_)
