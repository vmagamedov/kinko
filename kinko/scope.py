import copy
import functools


def _immutable(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        self_copy = copy.copy(self)
        func(self_copy, *args, **kwargs)
        return self_copy
    return wrapper


class Scope(object):

    def __init__(self, parent):
        self.parent = parent
        self.children = []
        self.vars = {}
        self.placeholders = {}

    def lookup(self, name):
        try:
            return self.vars[name]
        except KeyError:
            if self.parent is not None:
                return self.parent.lookup(name)
            else:
                raise LookupError('Undefined name "{}"'.format(name))

    def __copy__(self):
        self_copy = self.__class__.__new__(self.__class__)
        self_copy.__dict__ = {k: copy.copy(v)
                              for k, v in self.__dict__.items()}
        return self_copy

    @_immutable
    def add_child(self, child):
        self.children.append(child)
        self.placeholders.update(child.placeholders)

    @_immutable
    def define_symbol(self, name, type_):
        self.vars[name] = type_

    @_immutable
    def define_placeholder(self, name, type_):
        self.placeholders[name] = type_
