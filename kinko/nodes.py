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


class Keyword(Node):
    def __init__(self, name):
        self.name = name


class Placeholder(Node):
    def __init__(self, name):
        self.name = name


class Tuple(Node):
    def __init__(self, *values):
        self.values = values


class List(Node):
    pass
