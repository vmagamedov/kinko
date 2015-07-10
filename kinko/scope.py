from collections import namedtuple


Func = namedtuple('Func', 'name signature')


class Scope(object):

    def __init__(self, vars_, parent):
        self.vars = vars_
        self.parent = parent
        self.children = []
        self.functions = {}

    def lookup(self, sym):
        try:
            return self.vars[sym.name]
        except KeyError:
            if self.parent is not None:
                return self.parent.lookup(sym)
            else:
                raise

    def _copy(self):
        copy = type(self).__new__(type(self))
        copy.vars = self.vars.copy()
        copy.parent = self.parent
        copy.children = self.children[:]
        copy.functions = self.functions.copy()
        return copy

    def add(self, child):
        copy = self._copy()
        copy.children.append(child)
        return copy

    def define(self, name, ftype):
        copy = self._copy()
        copy.functions[name] = ftype
        return copy
