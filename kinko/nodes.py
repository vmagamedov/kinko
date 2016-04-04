from json.encoder import encode_basestring_ascii

from .compat import text_type


_undefined = object()


class Node(object):
    location = None

    def __init__(self, location=_undefined, type=_undefined):
        if location is not _undefined:
            self.location = location
        if type is not _undefined:
            self.__type__ = type

    def clone(self):
        cls = self.__class__
        clone = cls.__new__(cls)
        clone.__dict__ = self.__dict__.copy()
        return clone

    def clone_with(self, *args, **kwargs):
        clone = self.clone()
        clone.__init__(*args, **kwargs)
        return clone

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
        return node.clone_with(self.visit(i) for i in node.values)

    def visit_list(self, node):
        return node.clone_with(self.visit(i) for i in node.values)

    def visit_dict(self, node):
        return node.clone_with(self.visit(i) for i in node.values)

    def visit_symbol(self, node):
        return node.clone()

    def visit_keyword(self, node):
        return node.clone()

    def visit_placeholder(self, node):
        return node.clone()

    def visit_number(self, node):
        return node.clone()

    def visit_string(self, node):
        return node.clone()
