import re
try:
    from functools import reduce
except ImportError:
    pass

from .nodes import String, Symbol, Tuple, List, Placeholder
from .nodes import NodeVisitor, NodeTransformer
from .errors import UserError
from .tokenizer import Location, Position


class TransformError(UserError):
    pass


INTERPOLATION_RE = re.compile(r'\{[\w.-]+\}')


def _interpolate_string(node):
    line = node.location.start.line
    last_pos = 0
    val_offset = node.location.start.offset + 1
    val_column = node.location.start.column + 1

    def _step(delta):
        return Position(val_offset + delta, line,
                        val_column + delta)

    for match in INTERPOLATION_RE.finditer(node.value):
        sym = match.group()[1:-1]
        if not all(sym.split('.')):
            continue

        m_start, m_end = match.span()

        chunk = node.value[last_pos:m_start]
        if chunk:
            yield String(chunk,
                         location=Location((_step(last_pos) if last_pos
                                            else node.location.start),
                                           _step(m_start)))

        yield Symbol(sym, location=Location(_step(m_start + 1),
                                            _step(m_end - 1)))
        last_pos = m_end

    tail = node.value[last_pos:]
    if tail or not last_pos:
        yield String(tail,
                     location=Location((_step(last_pos) if last_pos
                                        else node.location.start),
                                       node.location.end))


class InterpolateString(NodeTransformer):

    def visit_string(self, node):
        nodes = list(_interpolate_string(node))
        if len(nodes) > 1:
            kw = {'location': node.location}
            return Tuple([Symbol('join', **kw), List(nodes, **kw)], **kw)
        else:
            return nodes[0]


def _translate_dots(node, node_cls):
    kw = {'location': node.location}
    path = [node.name] if '/' in node.name else node.name.split('.')

    def reducer(value, attr):
        return Tuple([Symbol('get', **kw), value, Symbol(attr, **kw)], **kw)

    return reduce(reducer, path[1:], node_cls(path[0], **kw))


class _TupleFirstValueValidator(NodeVisitor):

    def __init__(self, errors):
        self.errors = errors

    def visit_symbol(self, node):
        if not node.ns and '.' in node.name:
            with self.errors.location(node.location):
                raise TransformError('Symbol in this position should not '
                                     'contain dots')


class TranslateDots(NodeTransformer):

    def __init__(self, errors):
        self.validator = _TupleFirstValueValidator(errors)

    def visit_tuple(self, node):
        self.validator.visit(node.values[0])
        return super(TranslateDots, self).visit_tuple(node)

    def visit_symbol(self, node):
        return _translate_dots(node, Symbol)

    def visit_placeholder(self, node):
        return _translate_dots(node, Placeholder)
