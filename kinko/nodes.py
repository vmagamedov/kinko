class Node(object):
    __type__ = None

    @classmethod
    def typed(cls, _type_, *args, **kwargs):
        node = cls(*args, **kwargs)
        node.__type__ = _type_
        return node


class Symbol(Node):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)


class Keyword(Node):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)


class Placeholder(Node):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return '<{}({})>'.format(self.__class__.__name__, self.name)


class Tuple(Node):
    def __init__(self, *values):
        self.values = values


class List(Node):
    def __init__(self, *values):
        self.values = values


class Dict(Node):
    def __init__(self, *values):
        self.values = values
