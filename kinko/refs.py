from .nodes import NodeVisitor
from .types import TypeVarMeta, RecordMeta, ListTypeMeta, VarNamedArgsMeta
from .types import VarArgsMeta, NamedArgMeta, TypeRefMeta
from .utils import split_args, normalize_args
from .query import Edge, Link, Field, merge


class Reference(object):

    def __init__(self, backref):
        self.backref = backref


class ScalarRef(Reference):

    def __repr__(self):
        return '{!r} > scalar'.format(self.backref)


class ItemRef(Reference):

    def __repr__(self):
        return '{!r} > []'.format(self.backref)


class FieldRef(Reference):

    def __init__(self, backref, name):
        super(FieldRef, self).__init__(backref)
        self.name = name

    def __repr__(self):
        if self.backref:
            return '{!r} > [{!r}]'.format(self.backref, self.name)
        else:
            return 'ctx > [{!r}]'.format(self.name)


class ArgRef(Reference):

    def __init__(self, name):
        super(ArgRef, self).__init__(None)
        self.name = name

    def __repr__(self):
        return "#{}".format(self.name)


def get_origin(obj):
    if isinstance(obj, TypeVarMeta):
        if obj.__backref__ is not None:
            return get_origin(obj.__backref__)
    else:
        if obj.backref is not None:
            return get_origin(obj.backref)
    return obj


def is_from_arg(ref):
    return isinstance(get_origin(ref), ArgRef)


def get_type(type_):
    if isinstance(type_, TypeRefMeta):
        return type_.__ref__()
    return type_


def ref_to_req(var, add_req=None):
    if var is None:
        assert add_req is not None
        return add_req

    ref = var.__backref__
    inst = get_type(var.__instance__)

    if isinstance(inst, RecordMeta):
        if isinstance(ref, FieldRef):
            edge = Edge([]) if add_req is None else add_req
            return ref_to_req(ref.backref, Edge([Link(ref.name, edge)]))
        else:
            return ref_to_req(ref.backref, add_req)

    elif isinstance(inst, ListTypeMeta):
        item_type = get_type(inst.__item_type__)
        assert isinstance(ref, FieldRef), type(ref)
        assert isinstance(item_type, RecordMeta), type(item_type)
        edge = Edge([]) if add_req is None else add_req
        return ref_to_req(ref.backref, Edge([Link(ref.name, edge)]))

    else:
        assert isinstance(ref, FieldRef), type(ref)
        assert add_req is None, repr(add_req)
        return ref_to_req(ref.backref, Edge([Field(ref.name)]))


def type_to_query(type_):
    fields = []
    for f_name, f_type in type_.__items__.items():
        if isinstance(f_type, RecordMeta):
            fields.append(Link(f_name, type_to_query(f_type)))
        elif isinstance(f_type, ListTypeMeta):
            if isinstance(f_type.__item_type__, RecordMeta):
                fields.append(Link(f_name, type_to_query(f_type.item_type)))
            else:
                raise NotImplementedError
        else:
            fields.append(Field(f_name))
    return Edge(fields)


def node_ref(node):
    node_type = getattr(node, '__type__', None)
    if isinstance(node_type, TypeVarMeta) and node_type.__backref__:
        if not is_from_arg(node_type.__backref__):
            return node_type


class RefsCollector(NodeVisitor):

    def __init__(self):
        self.refs = {}
        self._acc = []
        self._calls = set([])

    @classmethod
    def collect(cls, node):
        self = cls()
        self.visit(node)
        return self.refs

    def type_ref(self, type_):
        if isinstance(type_, TypeVarMeta):
            if type_.__backref__ is not None:
                return self._ref_gen.visit(type_)
            else:
                return self.type_ref(type_.__instance__)

    def node_ref(self, node):
        return self.type_ref(getattr(node, '__type__', None))

    def visit(self, node):
        ref = node_ref(node)
        if ref is not None:
            self._acc.append(ref_to_req(ref))
        super(RefsCollector, self).visit(node)

    def _visit_arg(self, arg, fn_arg_type):
        arg_ref = node_ref(arg)
        if arg_ref is not None:
            if isinstance(fn_arg_type, RecordMeta):
                add_req = type_to_query(fn_arg_type)
            else:
                add_req = None
            self._acc.append(ref_to_req(arg_ref, add_req))

    def visit_tuple(self, node):
        sym, args = node.values[0], node.values[1:]
        if sym.name == 'def':
            name_sym, body = args[0], args[1:]
            # visit def's body
            assert not self._acc and not self._calls
            for item in body:
                self.visit(item)
            self.refs[name_sym.name] = merge(self._acc[:]), list(self._calls)
            del self._acc[:]
            self._calls.clear()
        else:
            self._calls.add(sym.name)
            fn_type = sym.__type__
            pos_args, kw_args = split_args(args)
            norm_args = normalize_args(fn_type, pos_args, kw_args)

            for arg, fn_arg_type in zip(norm_args, fn_type.__args__):
                if isinstance(fn_arg_type, VarNamedArgsMeta):
                    pass

                elif isinstance(fn_arg_type, VarArgsMeta):
                    pass

                elif isinstance(fn_arg_type, NamedArgMeta):
                    self._visit_arg(arg, fn_arg_type.__arg_type__)

                else:
                    self._visit_arg(arg, fn_arg_type)

            super(RefsCollector, self).visit_tuple(node)


def _yield_queries(mapping, func_name):
    query, calls = mapping[func_name]
    yield query
    for name in calls:
        if name in mapping:
            for item in _yield_queries(mapping, name):
                yield item


def extract(node):
    refs = RefsCollector.collect(node)
    return {name: merge(_yield_queries(refs, name))
            for name in refs}
