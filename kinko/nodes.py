class Node(object):

    def __init__(self, location=None):  # kwarg-only
        self.location = location

    @classmethod
    def typed(cls, _type_, *args, **kwargs):
        node = cls(*args, **kwargs)
        node.__type__ = _type_
        return node


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


class String(Node):

    def __init__(self, value, **kw):
        self.value = value
        super(String, self).__init__(**kw)

    def __repr__(self):
        return '"{}"'.format(self.value.replace('"', '\\"'))


class Number(Node):

    def __init__(self, value, **kw):
        self.value = value
        super(Number, self).__init__(**kw)

    def __repr__(self):
        return repr(self.value)


class Keyword(Node):

    def __init__(self, name, **kw):
        self.name = name
        super(Keyword, self).__init__(**kw)

    def __repr__(self):
        return ':{}'.format(self.name)


class Placeholder(Node):

    def __init__(self, name, **kw):
        self.name = name
        super(Placeholder, self).__init__(**kw)

    def __repr__(self):
        return '#{}'.format(self.name)


class Tuple(Node):

    def __init__(self, values, **kw):
        self.values = tuple(values)
        super(Tuple, self).__init__(**kw)

    def __repr__(self):
        return '({})'.format(' '.join(map(repr, self.values)))


class List(Node):

    def __init__(self, values, **kw):
        self.values = tuple(values)
        super(List, self).__init__(**kw)

    def __repr__(self):
        return '[{}]'.format(' '.join(map(repr, self.values)))


class Dict(Node):

    def __init__(self, values, **kw):
        self.values = tuple(values)
        super(Dict, self).__init__(**kw)

    def __repr__(self):
        return '{{{}}}'.format(' '.join(map(repr, self.values)))
