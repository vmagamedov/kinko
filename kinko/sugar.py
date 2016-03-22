import re
try:
    from functools import reduce
except ImportError:
    pass

from .nodes import String, Symbol, Tuple, List, NodeTransformer, Placeholder

INTERPOLATION_RE = re.compile(r'\{[\w.-]+\}')


def _interpolate_string(node):
    kw = {'location': node.location}
    last_pos = 0
    for match in INTERPOLATION_RE.finditer(node.value):
        sym = match.group()[1:-1]
        if not all(sym.split('.')):
            continue
        yield String(node.value[last_pos:match.start()], **kw)
        yield Symbol(sym, **kw)
        last_pos = match.end()
    yield String(node.value[last_pos:], **kw)


class InterpolateString(NodeTransformer):

    def visit_string(self, node):
        nodes = list(_interpolate_string(node))
        if len(nodes) > 1:
            kw = {'location': node.location}
            return Tuple([Symbol('join', **kw), List(nodes, **kw)], **kw)
        else:
            return node


def _translate_dots(node, node_cls):
    kw = {'location': node.location}
    head, sep, tail = node.name.partition('/')
    if sep:
        parts = tail.split('.')
        path = [head + sep + parts[0]] + parts[1:]
    else:
        path = head.split('.')

    def reducer(value, attr):
        return Tuple([Symbol('get', **kw), value, Symbol(attr, **kw)], **kw)

    return reduce(reducer, path[1:], node_cls(path[0], **kw))


class TranslateDots(NodeTransformer):

    def visit_symbol(self, node):
        return _translate_dots(node, Symbol)

    def visit_placeholder(self, node):
        return _translate_dots(node, Placeholder)
