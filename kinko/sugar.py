import re

from kinko.nodes import String, Symbol, Tuple, List, NodeTransformer

INTERPOLATION_RE = re.compile(r'\{[\w.-]+\}')


def _translate(node):
    last_pos = 0
    for match in INTERPOLATION_RE.finditer(node.value):
        sym = match.group()[1:-1]
        if not all(sym.split('.')):
            continue
        yield String(node.value[last_pos:match.start()])
        yield Symbol(sym)
        last_pos = match.end()
    yield String(node.value[last_pos:])


def translate(node):
    nodes = list(_translate(node))
    if len(nodes) > 1:
        return Tuple([Symbol('join'), List(nodes)])
    else:
        return node


class StringInterpolate(NodeTransformer):

    def visit_string(self, node):
        return translate(node)
