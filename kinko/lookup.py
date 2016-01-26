from .nodes import NodeVisitor
from .parser import parser
from .tokenizer import tokenize


class DependenciesVisitor(NodeVisitor):

    def __init__(self):
        self._dependencies = set([])

    @classmethod
    def get_dependencies(cls, node):
        visitor = cls()
        visitor.visit(node)
        return visitor._dependencies

    def visit_tuple(self, node):
        sym = node.values[0]
        if sym.ns:
            self._dependencies.add(sym.ns)
        super(DependenciesVisitor, self).visit_tuple(node)


class Namespace(object):

    def __init__(self, name, dependencies):
        self.name = name
        self.dependencies = dependencies


class Lookup(object):

    def __init__(self, loader):
        self.loader = loader
        self.namespaces = {}

    def load(self, name):
        src = self.loader.load(name)
        tokens = list(tokenize(src))
        node = parser().parse(tokens)
        dependencies = DependenciesVisitor.get_dependencies(node)
        self.namespaces[name] = Namespace(name, dependencies)
        for dependency in dependencies:
            self.load(dependency)

    def get(self, name):
        if name not in self.namespaces:
            self.load(name)
        return self.namespaces[name]
