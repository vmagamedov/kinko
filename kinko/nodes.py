from __future__ import absolute_import

from ast import literal_eval


class Node(object):
    __slots__ = ('__type__', 'location')

    def __init__(self, location=None):  # kwarg-only
        self.location = location

    @classmethod
    def typed(cls, _type_, *args, **kwargs):
        node = cls(*args, **kwargs)
        node.__type__ = _type_
        return node

    def __eq__(self, other):
        """Equals method for unit tests

        Discards location and type info. Probably may be replaced by some
        visitor for unit tests if better equals ever needed
        """
        # Note: We intentionally skip iherited slots
        for i in self.__slots__:
            if getattr(self, i) != getattr(other, i):
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        # Note: We intentionally skip iherited slots
        return '<{} {}>'.format(self.__class__.__name__,
            ' '.join('{}={}'.format(name, getattr(self, name))
                     for name in self.__slots__))


class Symbol(Node):
    __slots__ = ('name',)

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
    __slots__ = ('value',)

    def __init__(self, value, **kw):
        self.value = value
        super(String, self).__init__(**kw)

    def __repr__(self):
        return '<{}({!r})>'.format(self.__class__.__name__, self.value)

    @classmethod
    def from_token(String, tok):
        kind, value, location = tok
        # Note: tokenizer guarantee that value is always quoted string
        value = literal_eval(value)
        return String(value, location=location)


class Number(Node):
    __slots__ = ('value',)

    def __init__(self, value, **kw):
        self.value = value
        super(Number, self).__init__(**kw)

    @classmethod
    def from_token(Number, tok):
        kind, value, location = tok
        # Note: tokenizer guarantee that value consists of dots and digits
        # TODO(tailhook) convert exceptions
        value = literal_eval(value)
        return Number(value, location=location)


class Keyword(Node):
    __slots__ = ('name',)

    def __init__(self, name, **kw):
        self.name = name
        super(Keyword, self).__init__(**kw)

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)

    @classmethod
    def from_token(Keyword, tok):
        kind, value, location = tok
        return Keyword(value, location=location)


class KeywordPair(Node):
    __slots__ = ('keyword', 'value')

    def __init__(self, keyword, value, **kw):
        self.keyword = keyword
        self.value = value
        super(KeywordPair, self).__init__(**kw)


class Placeholder(Node):
    __slots__ = ('name',)

    def __init__(self, name, **kw):
        self.name = name
        super(Placeholder, self).__init__(**kw)

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)

    @classmethod
    def from_token(Placeholder, tok):
        kind, value, location = tok
        return Placeholder(value, location=location)


class Tuple(Node):
    __slots__ = ('symbol', 'args')

    def __init__(self, symbol, args, **kw):
        self.symbol = symbol
        self.args = args
        super(Tuple, self).__init__(**kw)

    def __repr__(self):
        return '<{} {} {}>'.format(self.__class__.__name__,
            self.symbol,
            ' '.join(map(repr, self.args)))


class List(Node):
    __slots__ = ('values',)

    def __init__(self, values, **kw):
        self.values = values
        super(List, self).__init__(**kw)


class Dict(Node):
    __slots__ = ('pairs',)

    def __init__(self, pairs, **kw):
        self.pairs = pairs
        super(Dict, self).__init__(**kw)


class Dotname(Node):
    __slots__ = ('item', 'attrs')

    def __init__(self, item, attrs, **kw):
        self.item = item
        self.attrs = attrs
        super(Dotname, self).__init__(**kw)
