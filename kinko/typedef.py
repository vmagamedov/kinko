import weakref

from . import types
from .utils import split_args
from .nodes import NodeTransformer, Symbol
from .parser import parse
from .tokenizer import tokenize


TYPES = {
    'Boolean': types.BoolType,
    'Nothing': types.BoolType,
    'String': types.StringType,
    'Integer': types.IntType,
    'Markup': types.Markup,
}

COMPOUND_TYPES = {
    'Union': lambda *t: types.Union[t],
    'Option': lambda t: types.Option[t],
    # TODO: implement var args and named args
    'Fn': lambda a, r: types.Func[a, r],
    'List': lambda t: types.ListType[t],
    'Dict': lambda k, v: types.DictType[k, v],
    'Record': lambda **kw: types.Record[kw],
}


class TypesConstructor(NodeTransformer):

    def __init__(self):
        self._types = {}

    def get_types(self):
        return self._types.copy()

    def visit_tuple_type(self, args):
        name_sym, type_value = args
        assert isinstance(name_sym, Symbol)
        self._types[name_sym.name] = self.visit(type_value)

    def visit_tuple(self, node):
        sym, args = node.values[0], node.values[1:]
        assert isinstance(sym, Symbol)
        if sym.name == 'type':
            return self.visit_tuple_type(args)
        elif sym.name in COMPOUND_TYPES:
            pos_args, kw_args = split_args([self.visit(arg) for arg in args])
            type_constructor = COMPOUND_TYPES[sym.name]
            # TODO: properly validate arguments
            return type_constructor(*pos_args, **kw_args)
        else:
            raise NotImplementedError('Unknown name: {}'.format(sym.name))

    def visit_list(self, node):
        return [self.visit(value) for value in node.values]

    def visit_dict(self, node):
        node_values = [self.visit(value) for value in node.values]
        keys, values = node_values[::2], node_values[1::2]
        return dict(zip(keys, values))

    def visit_symbol(self, node):
        if node.name in TYPES:
            return TYPES[node.name]
        else:
            return types.TypeRef[node.name]

    def visit_keyword(self, node):
        return node

    def visit_placeholder(self, node):
        raise NotImplementedError(repr(node))

    def visit_number(self, node):
        raise NotImplementedError(repr(node))

    def visit_string(self, node):
        raise NotImplementedError(repr(node))


class BindReferences(types.TypeVisitor):

    def __init__(self, types_):
        self._types = types_

    def visit_typeref(self, type_):
        type_.__ref__ = weakref.ref(self._types[type_.__ref_name__])


def load_types(src):
    tokens = list(tokenize(src))
    node = parse(tokens)
    types_constructor = TypesConstructor()
    types_constructor.visit(node)
    defs = types_constructor.get_types()
    ref_bind = BindReferences(defs)
    for value in defs.values():
        ref_bind.visit(value)
    return defs
