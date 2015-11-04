from kinko.nodes import NodeVisitor
from kinko.types import TypeVarMeta
from kinko.checker import split_args


class ContextVariable(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


class PositionalArgument(object):

    def __init__(self, pos):
        self.pos = pos

    def __repr__(self):
        return "#{}".format(self.pos)


class NamedArgument(object):

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "#{}".format(self.name)


class ListItem(object):

    def __init__(self, of):
        self.of = of

    def __repr__(self):
        return "{!r}[]".format(self.of)


class RecordField(object):

    def __init__(self, of, name):
        self.of = of
        self.name = name

    def __repr__(self):
        return "{!r}.{}".format(self.of, self.name)


class Apply(object):

    def __init__(self, func, args, kwargs):
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def __repr__(self):
        return "(apply {} {!r} {!r})".format(self.func, self.args, self.kwargs)


def _resolve_one(env, obj, args, kwargs):
    resolved_obj, = resolve(env, obj, args, kwargs)
    return resolved_obj


def resolve(env, obj, args, kwargs):
    if isinstance(obj, Apply):
        ra_args = [_resolve_one(env, a, args, kwargs) for a in obj.args]
        ra_kwargs = {k: _resolve_one(env, v, args, kwargs)
                     for k, v in obj.kwargs.items()}
        for ref in env.get(obj.func, []):
            for sub_ref in resolve(env, ref, ra_args, ra_kwargs):
                yield sub_ref
    elif isinstance(obj, PositionalArgument):
        yield args[obj.pos]
    elif isinstance(obj, NamedArgument):
        yield kwargs[obj.name]
    elif isinstance(obj, RecordField):
        yield RecordField(_resolve_one(env, obj.of, args, kwargs), obj.name)
    elif isinstance(obj, ListItem):
        yield ListItem(_resolve_one(env, obj.of, args, kwargs))
    else:
        yield obj


class RefsCollector(NodeVisitor):

    def __init__(self):
        self.refs = []

    def type_ref(self, type_):
        if type_.__ref__:
            return type_.__ref__
        if isinstance(type_, TypeVarMeta):
            return self.type_ref(type_.__instance__)

    def node_ref(self, node):
        if hasattr(node, '__type__'):
            return self.type_ref(node.__type__)
        return None

    def visit(self, node):
        ref = self.node_ref(node)
        if ref:
            self.refs.append(ref)
        super(RefsCollector, self).visit(node)

    def visit_tuple(self, node):
        sym, args = node.values[0], node.values[1:]
        pos_args, kw_args = split_args(args)
        pos_arg_refs = [self.node_ref(n) for n in pos_args]
        kw_arg_refs = {k: self.node_ref(v) for k, v in kw_args.items()}
        self.refs.append(Apply(sym.name, pos_arg_refs, kw_arg_refs))
        super(RefsCollector, self).visit_tuple(node)
