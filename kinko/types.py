class TypingMeta(type):

    def __init__(cls, *args, **kwargs):
        pass

    def __getitem__(cls, parameters):
        return cls.__class__(cls.__name__, cls.__bases__, dict(cls.__dict__),
                             parameters)


class FuncMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, parameters=(None, None)):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__args__, cls.__result__ = parameters
        return cls

    def __repr__(cls):
        return '{}[{!r}, {!r}]'.format(cls.__name__, cls.__args__,
                                       cls.__result__)

class Func(object):
    __metaclass__ = FuncMeta


class VarArgsMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, arg_type=None):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__arg_type__ = arg_type
        return cls

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__arg_type__)

class VarArgs(object):
    __metaclass__ = VarArgsMeta


class NamedArgMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, parameters=(None, None)):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__arg_name__, cls.__arg_type__ = parameters
        return cls

    def __repr__(cls):
        return '{}[{}={!r}]'.format(cls.__name__, cls.__arg_name__,
                                    cls.__arg_type__)

class NamedArg(object):
    __metaclass__ = NamedArgMeta


class QuotedMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, arg_type=None):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__arg_type__ = arg_type
        return cls

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__arg_type__)

class Quoted(object):
    __metaclass__ = QuotedMeta

    def __init__(self, value):
        self.__quoted_value__ = value


StringType = unicode
IntType = long


class DictTypeMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, parameters=(None, None)):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__key_type__, cls.__value_type__ = parameters
        return cls

    def __repr__(cls):
        return '{}[{!r}={!r}]'.format(cls.__name__, cls.__key_type__,
                                      cls.__value_type__)


class DictType(object):
    __metaclass__ = DictTypeMeta


class OutputType(object):
    pass


class SymbolType(object):
    pass


class CollectionType(object):
    class __metaclass__(TypingMeta):

        def __new__(typ, name, bases, namespace, item_type=None):
            cls = TypingMeta.__new__(typ, name, bases, namespace)
            cls.__item_type__ = item_type
            return cls

        def __repr__(cls):
            return '{}[{!r}]'.format(cls.__name__, cls.__item_type__)
