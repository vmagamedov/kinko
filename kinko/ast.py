class Node(object):

    def __repr__(self):
        # Note: We intentionally skip iherited slots
        return '<{} {}>'.format(self.__class__.__name__,
            ' '.join('{}={}'.format(name, getattr(self, name))
                     for name in self.__slots__))


class File(Node):
    __slots__ = ('functions',)

    def __init__(self, functions=[]):
        self.functions = functions


class Function(Node):
    __slots__ = ('name', 'arguments', 'body', 'vars')

    def __init__(self, name, body, arguments=[], vars={}):
        self.name = name
        self.body = body
        self.arguments = list(arguments)
        self.vars = dict(vars)


class Element(Node):
    __slots__ = ('name', 'attributes', 'body')

    def __init__(self, name, attributes, body):
        self.name = name
        self.attributes = attributes
        self.body = body


class GenericCall(Node):
    __slots__ = ('name', 'kwargs', 'args')

    def __init__(self, name, args, kwargs):
        self.name = name
        self.args = args
        self.kwargs = kwargs


class String(Node):
    __slots__ = ('value',)

    def __init__(self, value):
        self.value = value


class Attr(Node):
    __slots__ = ('expr', 'attr')

    def __init__(self, expr, attr):
        self.expr = expr
        self.attr = attr


class Name(Node):
    __slots__ = ('name',)

    def __init__(self, name):
        self.name = name
