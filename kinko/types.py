class TypingMeta(type):

    def __init__(cls, *args, **kwargs):
        pass

    def __getitem__(cls, parameters):
        return cls.__class__(cls.__name__, cls.__bases__, dict(cls.__dict__),
                             parameters)


class Func(object):
    class __metaclass__(TypingMeta):

        def __new__(typ, name, bases, namespace, parameters=(None, None)):
            cls = TypingMeta.__new__(typ, name, bases, namespace)
            cls.__args__, cls.__result__ = parameters
            return cls

        def __repr__(cls):
            return 'Func[{!r}, {!r}]'\
                .format(cls.__args__, cls.__result__)


class VarArgs(object):
    class __metaclass__(TypingMeta):

        def __new__(typ, name, bases, namespace, arg_type=None):
            cls = TypingMeta.__new__(typ, name, bases, namespace)
            cls.__arg_type__ = arg_type
            return cls

        def __repr__(cls):
            return 'VarArgs[{!r}]'\
                .format(cls.__arg_type__)


class NamedArg(object):
    class __metaclass__(TypingMeta):

        def __new__(typ, name, bases, namespace, parameters=(None, None)):
            cls = TypingMeta.__new__(typ, name, bases, namespace)
            cls.__arg_name__, cls.__arg_type__ = parameters
            return cls

        def __repr__(cls):
            return 'NamedArg[{}={!r}]'\
                .format(cls.__arg_name__, cls.__arg_type__)


StringType = unicode
IntType = long


class DictType(object):
    pass


class OutputType(object):
    pass


class SymbolType(object):
    pass


class CollectionType(object):
    pass
