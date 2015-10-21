from .compat import with_metaclass


class GenericMeta(type):

    def __repr__(cls):
        return cls.__name__

    def accept(self, visitor):
        raise NotImplementedError


class BoolTypeMeta(GenericMeta):

    def accept(cls, visitor):
        return visitor.visit_bool(cls)


class BoolType(with_metaclass(BoolTypeMeta, object)):
    pass


class NothingMeta(BoolTypeMeta):

    def accept(cls, visitor):
        return visitor.visit_nothing(cls)


class Nothing(with_metaclass(NothingMeta, object)):
    pass


class StringTypeMeta(BoolTypeMeta):

    def accept(cls, visitor):
        return visitor.visit_string(cls)


class StringType(with_metaclass(StringTypeMeta, object)):
    pass


class IntTypeMeta(BoolTypeMeta):

    def accept(cls, visitor):
        return visitor.visit_int(cls)


class IntType(with_metaclass(IntTypeMeta, object)):
    pass


class OutputTypeMeta(GenericMeta):

    def accept(cls, visitor):
        return visitor.visit_output(cls)


class OutputType(with_metaclass(OutputTypeMeta, object)):
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

    def accept(cls, visitor):
        return visitor.visit_typevar(cls)


class TypeVar(with_metaclass(TypeVarMeta, object)):
    pass


class UnionMeta(TypingMeta):

    def __cls_init__(cls, types):
        cls.__types__ = set(types)

    def __repr__(cls):
        return '{}[{}]'.format(cls.__name__,
                               '|'.join(map(repr, cls.__types__)))

    def accept(cls, visitor):
        return visitor.visit_union(cls)


class Union(with_metaclass(UnionMeta, object)):
    pass


class OptionMeta(UnionMeta):

    def __cls_init__(cls, type_):
        super(OptionMeta, cls).__cls_init__((type_, Nothing))

    def __repr__(cls):
        type_ = (cls.__types__ - {Nothing}).pop()
        return '{}[{!r}]'.format(cls.__name__, type_)

    def accept(cls, visitor):
        return visitor.visit_option(cls)


class Option(with_metaclass(OptionMeta, object)):
    pass


class FuncMeta(TypingMeta):

    def __cls_init__(cls, params):
        cls.__args__, cls.__result__ = params

    def __repr__(cls):
        return '{}[{!r}, {!r}]'.format(cls.__name__, cls.__args__,
                                       cls.__result__)

    def accept(cls, visitor):
        return visitor.visit_func(cls)


class Func(with_metaclass(FuncMeta, object)):
    pass


class VarArgsMeta(TypingMeta):

    def __cls_init__(cls, arg_type):
        cls.__arg_type__ = arg_type

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__arg_type__)

    def accept(cls, visitor):
        return visitor.visit_varargs(cls)


class VarArgs(with_metaclass(VarArgsMeta, object)):
    pass


class NamedArgMeta(TypingMeta):

    def __cls_init__(cls, params):
        cls.__arg_name__, cls.__arg_type__ = params

    def __repr__(cls):
        return '{}[{}={!r}]'.format(cls.__name__, cls.__arg_name__,
                                    cls.__arg_type__)

    def accept(cls, visitor):
        return visitor.visit_namedarg(cls)


class NamedArg(with_metaclass(NamedArgMeta, object)):
    pass


class ListTypeMeta(TypingMeta):

    def __cls_init__(cls, item_type):
        cls.__item_type__ = item_type

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__item_type__)

    def accept(cls, visitor):
        return visitor.visit_list(cls)


class ListType(with_metaclass(ListTypeMeta, object)):
    pass


class DictTypeMeta(TypingMeta):

    def __cls_init__(cls, params):
        cls.__key_type__, cls.__value_type__ = params

    def __repr__(cls):
        return '{}[{!r}={!r}]'.format(cls.__name__, cls.__key_type__,
                                      cls.__value_type__)

    def accept(cls, visitor):
        return visitor.visit_dict(cls)


class DictType(with_metaclass(DictTypeMeta, object)):
    pass


class RecordTypeMeta(TypingMeta):

    def __cls_init__(cls, items):
        cls.__items__ = dict(items)

    def __repr__(cls):
        return '{}[{!r}]'.format(cls.__name__, cls.__items__)

    def accept(cls, visitor):
        return visitor.visit_record(cls)


class RecordType(with_metaclass(RecordTypeMeta, object)):
    pass


class TypeTransformer(object):

    def visit(self, type_):
        return type_.accept(self)

    def visit_bool(self, type_):
        return type_

    def visit_nothing(self, type_):
        return type_

    def visit_string(self, type_):
        return type_

    def visit_int(self, type_):
        return type_

    def visit_output(self, type_):
        return type_

    def visit_typevar(self, type_):
        return TypeVar[self.visit(type_.__instance__)
                       if type_.__instance__ is not None else None]

    def visit_union(self, type_):
        return Union[(self.visit(t) for t in type_.__types__)]

    def visit_option(self, type_):
        t = (type_.__types__ - {Nothing}).pop()
        return Option[self.visit(t)]

    def visit_func(self, type_):
        return Func[[self.visit(t) for t in type_.__args__],
                    self.visit(type_.__result__)]

    def visit_varargs(self, type_):
        return VarArgs[self.visit(type_.__arg_type__)]

    def visit_namedarg(self, type_):
        return NamedArg[type_.__arg_name__, self.visit(type_.__arg_type__)]

    def visit_list(self, type_):
        return ListType[self.visit(type_.__item_type__)]

    def visit_dict(self, type_):
        return DictType[self.visit(type_.__key_type__),
                        self.visit(type_.__value_type__)]

    def visit_record(self, type_):
        return RecordType[{key: self.visit(value)
                           for key, value in type_.__items__.items()}]
