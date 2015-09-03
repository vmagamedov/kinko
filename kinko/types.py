from .compat import with_metaclass


class GenericMeta(type):

    def __repr__(cls):
        return cls.__name__


class Generic(with_metaclass(GenericMeta, object)):
    pass


def _subclass(*types):
    return type('T', tuple(types), {})


class BoolTypeMeta(GenericMeta):
    pass


class BoolType(with_metaclass(BoolTypeMeta, object)):
    pass


class StringType(with_metaclass(_subclass(BoolTypeMeta), object)):
    pass


class IntType(with_metaclass(_subclass(BoolTypeMeta), object)):
    pass


class OutputType(with_metaclass(_subclass(GenericMeta), object)):
    pass


class TypingMeta(GenericMeta):

    def __cls_init__(cls, *args):
        raise NotImplementedError

    def __getitem__(cls, parameters):
        type_ = cls.__class__(cls.__name__, cls.__bases__, dict(cls.__dict__))
        type_.__cls_init__(parameters)
        return type_


class TypeVarMeta(TypingMeta):

    def __cls_init__(cls, instance):
        cls.__instance__ = instance

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__instance__)


class TypeVar(with_metaclass(TypeVarMeta, object)):
    pass


class UnionMeta(TypingMeta):

    def __cls_init__(cls, types):
        cls.__types__ = (types,) if not isinstance(types, tuple) else types

    def __repr__(cls):
        return '{}[{}]'.format(cls.__name__,
                               '|'.join(map(repr, cls.__types__)))


class Union(with_metaclass(UnionMeta, object)):
    pass


class FuncMeta(TypingMeta):

    def __cls_init__(cls, params):
        cls.__args__, cls.__result__ = params

    def __repr__(cls):
        return '{}[{!r}, {!r}]'.format(cls.__name__, cls.__args__,
                                       cls.__result__)


class Func(with_metaclass(FuncMeta, object)):
    pass


class VarArgsMeta(TypingMeta):

    def __cls_init__(cls, arg_type):
        cls.__arg_type__ = arg_type

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__arg_type__)


class VarArgs(with_metaclass(VarArgsMeta, object)):
    pass


class NamedArgMeta(TypingMeta):

    def __cls_init__(cls, params):
        cls.__arg_name__, cls.__arg_type__ = params

    def __repr__(cls):
        return '{}[{}={!r}]'.format(cls.__name__, cls.__arg_name__,
                                    cls.__arg_type__)


class NamedArg(with_metaclass(NamedArgMeta, object)):
    pass


class QuotedMeta(TypingMeta):

    def __cls_init__(cls, arg_type):
        cls.__arg_type__ = arg_type

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__arg_type__)


class Quoted(with_metaclass(QuotedMeta, object)):
    pass


class ListTypeMeta(TypingMeta):

    def __cls_init__(cls, item_type):
        cls.__item_type__ = item_type

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__item_type__)


class ListType(with_metaclass(ListTypeMeta, object)):
    pass


class DictTypeMeta(TypingMeta):

    def __cls_init__(cls, params):
        cls.__key_type__, cls.__value_type__ = params

    def __repr__(cls):
        return '{}[{!r}={!r}]'.format(cls.__name__, cls.__key_type__,
                                      cls.__value_type__)


class DictType(with_metaclass(DictTypeMeta, object)):
    pass


class RecordTypeMeta(TypingMeta):

    def __cls_init__(cls, items):
        cls.__items__ = items.copy()

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__items__)


class RecordType(with_metaclass(RecordTypeMeta, object)):
    pass
