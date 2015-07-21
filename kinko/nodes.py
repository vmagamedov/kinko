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
        super(Symbol, self).__init__(**kw)

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)

    @classmethod
    def from_token(Symbol, tok):
        kind, value, location = tok
        return Symbol(value, location=location)


class String(Node):

    def __init__(self, value, **kw):
        self.value = value
        super(String, self).__init__(**kw)

    def __repr__(self):
        return '<{}({!r})>'.format(self.__class__.__name__, self.value)


class Number(Node):

    def __init__(self, value, **kw):
        self.value = value
        super(Number, self).__init__(**kw)


class Keyword(Node):

    def __init__(self, name, **kw):
        self.name = name
        super(Keyword, self).__init__(**kw)

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)


class KeywordPair(Node):

    def __init__(self, keyword, value, **kw):
        self.keyword = keyword
        self.value = value
        super(KeywordPair, self).__init__(**kw)


class Placeholder(Node):

    def __init__(self, name, **kw):
        self.name = name
        super(Placeholder, self).__init__(**kw)

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)


class Tuple(Node):

    def __init__(self, symbol, args, **kw):
        self.symbol = symbol
        self.args = args
        super(Tuple, self).__init__(**kw)

    def __repr__(self):
        return '<{} {} {}>'.format(self.__class__.__name__,
                                   self.symbol,
                                   ' '.join(map(repr, self.args)))


class List(Node):

    def __init__(self, values, **kw):
        self.values = values
        super(List, self).__init__(**kw)


class Dict(Node):

    def __init__(self, pairs, **kw):
        self.pairs = pairs
        super(Dict, self).__init__(**kw)


class Dotname(Node):

    def __init__(self, item, attrs, **kw):
        self.item = item
        self.attrs = attrs
        super(Dotname, self).__init__(**kw)
