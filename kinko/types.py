from .compat import with_metaclass


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

class Func(with_metaclass(FuncMeta, object)):
    pass


class VarArgsMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, arg_type=None):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__arg_type__ = arg_type
        return cls

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__arg_type__)

class VarArgs(with_metaclass(VarArgsMeta, object)):
    pass


class NamedArgMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, parameters=(None, None)):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__arg_name__, cls.__arg_type__ = parameters
        return cls

    def __repr__(cls):
        return '{}[{}={!r}]'.format(cls.__name__, cls.__arg_name__,
                                    cls.__arg_type__)

class NamedArg(with_metaclass(NamedArgMeta, object)):
    pass


class QuotedMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, arg_type=None):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__arg_type__ = arg_type
        return cls

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__arg_type__)

class Quoted(with_metaclass(QuotedMeta, object)):

    def __init__(self, value):
        self.__quoted_value__ = value


class StringType(object):
    pass


class IntType(object):
    pass


class DictTypeMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, parameters=(None, None)):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__key_type__, cls.__value_type__ = parameters
        return cls

    def __repr__(cls):
        return '{}[{!r}={!r}]'.format(cls.__name__, cls.__key_type__,
                                      cls.__value_type__)


class DictType(with_metaclass(DictTypeMeta, object)):
    pass


class OutputType(object):
    pass


class SymbolType(object):
    pass


class CollectionTypeMeta(TypingMeta):

    def __new__(typ, name, bases, namespace, item_type=None):
        cls = TypingMeta.__new__(typ, name, bases, namespace)
        cls.__item_type__ = item_type
        return cls

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__item_type__)


class CollectionType(with_metaclass(CollectionTypeMeta, object)):
    pass
