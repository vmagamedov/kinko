from ..nodes import Keyword, Dict, List


class QueryGenerator(object):

    def visit(self, node):
        return node.accept(self)

    def visit_attr(self, node):
        return Keyword(node.name)

    def visit_link(self, node):
        return Dict([Keyword(node.name), self.visit(node.edge)])

    def visit_edge(self, node):
        names = sorted(node.attrs.keys())
        return List([self.visit(node.attrs[name]) for name in names])


def to_query(pattern):
    query = QueryGenerator().visit(pattern)
    return query
