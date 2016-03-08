from itertools import chain
from collections import defaultdict


class Field(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return ':{}'.format(self.name)

    def accept(self, visitor):
        return visitor.visit_field(self)


class Link(object):

    def __init__(self, name, edge):
        self.name = name
        self.edge = edge

    def __repr__(self):
        return '{{:{} {!r}}}'.format(self.name, self.edge)

    def accept(self, visitor):
        return visitor.visit_link(self)


class Edge(object):

    def __init__(self, fields):
        self.fields = {field.name: field for field in fields}

    def add(self, field):
        return self.fields.setdefault(field.name, field)

    def __repr__(self):
        return '[{}]'.format(' '.join(map(repr, self.fields.values())))

    def accept(self, visitor):
        return visitor.visit_edge(self)


def _merge(edges):
    to_merge = defaultdict(list)
    for field in chain.from_iterable(e.fields.values() for e in edges):
        if field.__class__ is Link:
            to_merge[field.name].append(field.edge)
        else:
            yield field
    for name, values in to_merge.items():
        yield Link(name, Edge(_merge(values)))


def merge(edges):
    return Edge(_merge(edges))
