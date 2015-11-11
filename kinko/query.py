from .refs import ReferenceVisitor, RecordFieldRef
from .nodes import Keyword, Dict, List


class Attr(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return ':{}'.format(self.name)

    def accept(self, visitor):
        return visitor.visit_attr(self)


class Link(Attr):

    def __init__(self, name, edge):
        super(Link, self).__init__(name)
        self.edge = edge

    def __repr__(self):
        return '{{:{} {!r}}}'.format(self.name, self.edge)

    def accept(self, visitor):
        return visitor.visit_link(self)


class Edge(object):

    def __init__(self, attrs):
        self.attrs = {attr.name: attr for attr in attrs}

    def add(self, attr):
        return self.attrs.setdefault(attr.name, attr)

    def __repr__(self):
        return '[{}]'.format(' '.join(map(repr, self.attrs.values())))

    def accept(self, visitor):
        return visitor.visit_edge(self)


class QueryGenerator(object):

    def visit(self, node):
        return node.accept(self)

    def visit_attr(self, node):
        return Keyword(node.name)

    def visit_link(self, node):
        return Dict([Keyword(node.name), self.visit(node.edge)])

    def visit_edge(self, node):
        return List([self.visit(attr) for attr in node.attrs.values()])


class RefPathExtractor(ReferenceVisitor):

    def __init__(self):
        self._stack = [Edge([])]

    def _add_attr(self, ref):
        self._stack[-1].add(Attr(ref.backref.name))

    def _push_stack(self, ref):
        top = self._stack[-1]
        nxt = top.add(Link(ref.backref.name, Edge([])))
        self._stack.append(nxt.edge)

    def visit_scalar(self, ref):
        super(RefPathExtractor, self).visit_scalar(ref)
        self._add_attr(ref)

    def visit_list(self, ref):
        super(RefPathExtractor, self).visit_list(ref)
        if isinstance(ref.backref, RecordFieldRef):
            self._push_stack(ref)

    def visit_record(self, ref):
        super(RefPathExtractor, self).visit_record(ref)
        if isinstance(ref.backref, RecordFieldRef):
            self._push_stack(ref)

    def apply(self, ref):
        self.visit(ref)
        del self._stack[1:]

    def root(self):
        return self._stack[0]


def gen_query(refs):
    extractor = RefPathExtractor()
    for ref in refs:
        extractor.apply(ref)
    graph = extractor.root()
    query = QueryGenerator().visit(graph)
    return query
