from .nodes import NodeVisitor
from .types import TypeVarMeta, RecordMeta, ListTypeMeta
from .utils import split_args


class Reference(object):

    def __init__(self, backref):
        self.backref = backref

    def accept(self, visitor):
        raise NotImplementedError


class ScalarRef(Reference):

    def __repr__(self):
        return '{!r} > scalar'.format(self.backref)

    def accept(self, visitor):
        return visitor.visit_scalar(self)


class ListRef(Reference):

    def __repr__(self):
        return '{!r} > list'.format(self.backref)

    def accept(self, visitor):
        return visitor.visit_list(self)


class ListItemRef(Reference):

    def __repr__(self):
        return '{!r} > []'.format(self.backref)

    def accept(self, visitor):
        return visitor.visit_listitem(self)


class RecordRef(Reference):

    def __repr__(self):
        return '{!r} > record'.format(self.backref) if self.backref else 'ctx'

    def accept(self, visitor):
        return visitor.visit_record(self)


class RecordFieldRef(Reference):

    def __init__(self, backref, name):
        super(RecordFieldRef, self).__init__(backref)
        self.name = name

    def __repr__(self):
        if self.backref:
            return '{!r} > [{!r}]'.format(self.backref, self.name)
        else:
            return 'ctx > [{!r}]'.format(self.name)

    def accept(self, visitor):
        return visitor.visit_recordfield(self)


class ReferenceVisitor(object):

    def visit(self, ref):
        if ref is not None:
            ref.accept(self)

    def visit_scalar(self, ref):
        self.visit(ref.backref)

    def visit_list(self, ref):
        self.visit(ref.backref)

    def visit_listitem(self, ref):
        self.visit(ref.backref)

    def visit_record(self, ref):
        self.visit(ref.backref)

    def visit_recordfield(self, ref):
        self.visit(ref.backref)


class PosArgRef(Reference):

    def __init__(self, pos):
        super(PosArgRef, self).__init__(None)
        self.pos = pos

    def __repr__(self):
        return "#{}".format(self.pos)

    def accept(self, visitor):
        return visitor.visit_posarg(self)


class NamedArgRef(Reference):

    def __init__(self, name):
        super(NamedArgRef, self).__init__(None)
        self.name = name

    def __repr__(self):
        return "#{}".format(self.name)

    def accept(self, visitor):
        return visitor.visit_namedarg(self)


class Apply(Reference):

    def __init__(self, func, args, kwargs):
        super(Apply, self).__init__(None)
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return "(apply {} {!r} {!r})".format(self.func, self.args, self.kwargs)

    def accept(self, visitor):
        raise NotImplementedError


class ArgsResolver(object):

    def __init__(self, args, kwargs):
        self.args = args
        self.kwargs = kwargs

    def visit(self, ref):
        return ref.accept(self)

    def visit_scalar(self, ref):
        return ScalarRef(self.visit(ref.backref))

    def visit_list(self, ref):
        return ListRef(self.visit(ref.backref))

    def visit_listitem(self, ref):
        return ListItemRef(self.visit(ref.backref))

    def visit_record(self, ref):
        return RecordRef(self.visit(ref.backref))

    def visit_recordfield(self, ref):
        backref = None if ref.backref is None else self.visit(ref.backref)
        return RecordFieldRef(backref, ref.name)

    def visit_posarg(self, ref):
        return self.args[ref.pos].backref

    def visit_namedarg(self, ref):
        return self.kwargs[ref.name].backref


def expand_apply(env, apl, args, kwargs):
    res = ArgsResolver(args, kwargs)
    for ref in env.get(apl.func, []):
        if isinstance(ref, Apply):
            sub_args = [(a and res.visit(a)) for a in ref.args]
            sub_kwargs = {k: (v and res.visit(v))
                          for k, v in ref.kwargs.items()}
            for sub_ref in expand_apply(env, ref, sub_args, sub_kwargs):
                yield sub_ref
        else:
            yield res.visit(ref)


def resolve_refs(env, name):
    return list(expand_apply(env, Apply(name, [], {}), [], {}))


def prune(t):
    while isinstance(t, TypeVarMeta):
        t = t.__instance__
    return t


class RefGen(object):

    def visit(self, obj):
        if obj is not None:
            return obj.accept(self)

    def visit_listitem(self, ref):
        return ListItemRef(self.visit(ref.backref))

    def visit_recordfield(self, ref):
        return RecordFieldRef(self.visit(ref.backref), ref.name)

    def visit_posarg(self, ref):
        return ref

    def visit_namedarg(self, ref):
        return ref

    def visit_typevar(self, var):
        inst = prune(var)
        if inst is None:
            return None
        elif isinstance(inst, ListTypeMeta):
            return ListRef(self.visit(var.__backref__))
        elif isinstance(inst, RecordMeta):
            return RecordRef(self.visit(var.__backref__))
        else:
            return ScalarRef(self.visit(var.__backref__))


class RefsCollector(NodeVisitor):

    def __init__(self):
        self.refs = {}
        self._acc = []
        self._ref_gen = RefGen()

    def type_ref(self, type_):
        if isinstance(type_, TypeVarMeta):
            if type_.__backref__ is not None:
                return self._ref_gen.visit(type_)
            else:
                return self.type_ref(type_.__instance__)

    def node_ref(self, node):
        return self.type_ref(getattr(node, '__type__', None))

    def visit(self, node):
        ref = self.node_ref(node)
        if ref:
            self._acc.append(ref)
        super(RefsCollector, self).visit(node)

    def visit_tuple(self, node):
        sym, args = node.values[0], node.values[1:]
        if sym.name == 'def':
            name_sym, body = args[0], args[1:]
            # visit def's body
            assert not self._acc
            for item in body:
                self.visit(item)
            self.refs[name_sym.name] = self._acc[:]
            del self._acc[:]
        else:
            pos_args, kw_args = split_args(args)
            pos_arg_refs = [self.node_ref(n) for n in pos_args]
            kw_arg_refs = {k: self.node_ref(v) for k, v in kw_args.items()}
            self._acc.append(Apply(sym.name, pos_arg_refs, kw_arg_refs))
            super(RefsCollector, self).visit_tuple(node)
