from .nodes import NodeVisitor


class Printer(NodeVisitor):

    def __init__(self):
        self._buffer = []

    @classmethod
    def dumps(cls, node):
        printer = cls()
        printer.visit(node)
        # return '\n'.join(printer._buffer) + '\n'
        return repr(node) + '\n'

    def visit_tuple(self, node):
        super(Printer, self).visit_tuple(node)
