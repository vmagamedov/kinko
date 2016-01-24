from json.encoder import encode_basestring_ascii

from .compat import text_type


class Node(object):

    def __init__(self, location=None):  # kwarg-only
        self.location = location

    @classmethod
    def typed(cls, _type_, *args, **kwargs):
        node = cls(*args, **kwargs)
        node.__type__ = _type_
        return node

    def accept(self, visitor):
        raise NotImplementedError


class Symbol(Node):

    def __init__(self, name, **kw):
        self.name = name
        head, sep, tail = name.partition('/')
        if sep:
            self.ns, self.rel = head, tail
        else:
            self.ns, self.rel = None, name
        super(Symbol, self).__init__(**kw)

    def __repr__(self):
        return self.name

    def accept(self, visitor):
        return visitor.visit_symbol(self)


class String(Node):

    def __init__(self, value, **kw):
        self.value = text_type(value)
        super(String, self).__init__(**kw)

    def __repr__(self):
        return encode_basestring_ascii(self.value)

    def accept(self, visitor):
        return visitor.visit_string(self)


class Number(Node):

    def __init__(self, value, **kw):
        self.value = value
        super(Number, self).__init__(**kw)

    def __repr__(self):
        return repr(self.value)

    def accept(self, visitor):
        return visitor.visit_number(self)


class Keyword(Node):

    def __init__(self, name, **kw):
        self.name = name
        super(Keyword, self).__init__(**kw)

    def __repr__(self):
        return ':{}'.format(self.name)

    def accept(self, visitor):
        return visitor.visit_keyword(self)


class Placeholder(Node):

    def __init__(self, name, **kw):
        self.name = name
        super(Placeholder, self).__init__(**kw)

    def __repr__(self):
        return '#{}'.format(self.name)

    def accept(self, visitor):
        return visitor.visit_placeholder(self)


class Tuple(Node):

    def __init__(self, values, **kw):
        self.values = tuple(values)
        super(Tuple, self).__init__(**kw)

    def __repr__(self):
        return '({})'.format(' '.join(map(repr, self.values)))

    def accept(self, visitor):
        return visitor.visit_tuple(self)


class List(Node):

    def __init__(self, values, **kw):
        self.values = tuple(values)
        super(List, self).__init__(**kw)

    def __repr__(self):
        return '[{}]'.format(' '.join(map(repr, self.values)))

    def accept(self, visitor):
        return visitor.visit_list(self)


class Dict(Node):

    def __init__(self, values, **kw):
        self.values = tuple(values)
        super(Dict, self).__init__(**kw)

    def __repr__(self):
        return '{{{}}}'.format(' '.join(map(repr, self.values)))

    def accept(self, visitor):
        return visitor.visit_dict(self)


class NodeVisitor(object):

    def visit(self, node):
        node.accept(self)

    def visit_tuple(self, node):
        for value in node.values:
            self.visit(value)

    def visit_list(self, node):
        for value in node.values:
            self.visit(value)

    def visit_dict(self, node):
        for value in node.values:
            self.visit(value)

    def visit_symbol(self, node):
        pass

    def visit_keyword(self, node):
        pass

    def visit_placeholder(self, node):
        pass

    def visit_number(self, node):
        pass

    def visit_string(self, node):
        pass


class NodeTransformer(object):

    def visit(self, node):
        return node.accept(self)

    def visit_tuple(self, node):
        return Tuple([self.visit(i) for i in node.values])

    def visit_list(self, node):
        return List([self.visit(i) for i in node.values])

    def visit_dict(self, node):
        return Dict([self.visit(i) for i in node.values])

    def visit_symbol(self, node):
        return Symbol(node.name)

    def visit_keyword(self, node):
        return Keyword(node.name)

    def visit_placeholder(self, node):
        return Placeholder(node.name)

    def visit_number(self, node):
        return Number(node.value)

    def visit_string(self, node):
        return String(node.value)
