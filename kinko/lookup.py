from collections import namedtuple

from .nodes import NodeVisitor
from .utils import Buffer
from .parser import parser
from .compat import _exec_in
from .checker import def_types, split_defs, Environ, check, collect_defs
from .checker import NamesResolver, NamesUnResolver
from .loaders import DictCache
from .tokenizer import tokenize
from .out.py.compiler import compile_module


class DependenciesVisitor(NodeVisitor):

    def __init__(self):
        self._dependencies = set([])

    @classmethod
    def get_dependencies(cls, node):
        visitor = cls()
        visitor.visit(node)
        return visitor._dependencies

    def visit_tuple(self, node):
        sym = node.values[0]
        if sym.ns:
            self._dependencies.add(sym.ns)
        super(DependenciesVisitor, self).visit_tuple(node)


Namespace = namedtuple('Namespace',
                       'name modified_time module dependencies')

ParsedSource = namedtuple('ParsedSource',
                          'name modified_time node dependencies')


class SimpleContext(object):

    def __init__(self, result):
        self.buffer = Buffer()
        self.result = result


class Context(SimpleContext):

    def __init__(self, lookup, result):
        self._lookup = lookup
        super(Context, self).__init__(result)

    def lookup(self, name):
        ns, _, fn_name = name.partition('/')
        return self._lookup.get(ns).module[fn_name]


class Lookup(object):

    def __init__(self, types, loader, cache=None):
        self.types = types
        self.loader = loader
        self.cache = cache or DictCache()
        self.namespaces = {}
        self._parser = parser()

    def _get_dependencies(self, ns, _visited=None):
        _visited = set([]) if _visited is None else _visited
        if ns.name not in _visited:
            _visited.add(ns.name)
            yield ns
            for dep_name in ns.dependencies:
                dep = self.namespaces[dep_name]
                for item in self._get_dependencies(dep, _visited=_visited):
                    yield item

    def _load_sources(self, name, _visited=None):
        _visited = set([]) if _visited is None else _visited
        if name not in _visited:
            _visited.add(name)
            source = self.loader.load(name)
            node = self._parser.parse(list(tokenize(source.content)))
            node = NamesResolver(source.name).visit(node)
            dependencies = DependenciesVisitor.get_dependencies(node)
            yield ParsedSource(name, source.modified_time, node, dependencies)
            for dep in dependencies:
                for item in self._load_sources(dep, _visited=_visited):
                    yield item

    def _check(self, parsed_sources):
        env = dict(self.types)

        node = collect_defs(ps.node for ps in parsed_sources)
        env.update(def_types(node))

        environ = Environ(env)
        node = check(node, environ)

        modules = {ns: NamesUnResolver(ns).visit(mod)
                   for ns, mod in split_defs(node).items()}

        return [ps._replace(node=modules[ps.name])
                for ps in parsed_sources]

    def _compile_module(self, name, module):
        module_code = compile(module, '<kinko:{}>'.format(name), 'exec')
        globals_dict = {}
        _exec_in(module_code, globals_dict)
        return globals_dict

    def load(self, name):
        ns = self.namespaces.get(name)
        if ns is not None:
            deps = list(self._get_dependencies(ns))
            if all(self.loader.is_uptodate(dep) for dep in deps):
                return

        parsed_sources = list(self._load_sources(name))
        checked_sources = self._check(parsed_sources)

        modules = {cs.name: compile_module(cs.node) for cs in checked_sources}
        compiled_modules = {name: self._compile_module(name, module)
                            for name, module in modules.items()}

        for src in parsed_sources:
            self.namespaces[src.name] = Namespace(src.name, src.modified_time,
                                                  compiled_modules[src.name],
                                                  src.dependencies)

    def get(self, name):
        self.load(name)
        return self.namespaces[name]

    def render(self, name, result):
        ctx = Context(self, result)
        ctx.buffer.push()
        fn = ctx.lookup(name)
        fn(ctx)
        return ctx.buffer.pop()
