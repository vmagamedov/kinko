import logging
from collections import namedtuple

from .refs import extract
from .nodes import NodeVisitor
from .utils import Buffer
from .parser import parse
from .errors import UserError, WARNING, ERROR, Errors
from .compat import _exec_in
from .checker import def_types, split_defs, Environ, check, collect_defs
from .checker import NamesResolver, NamesUnResolver
from .loaders import DictCache
from .tokenizer import tokenize
from .compile.python import compile_module


log = logging.getLogger(__name__)


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


class Function(object):

    def __init__(self, lookup, name):
        self._lookup = lookup
        self.name = name

    def query(self):
        return self._lookup._get_query(self.name)

    def render(self, result):
        return self._lookup._render(self.name, result)


class Context(SimpleContext):

    def __init__(self, lookup, result):
        self._lookup = lookup
        super(Context, self).__init__(result)
        self.builtins = lookup.builtins

    def lookup(self, name):
        ns, _, fn_name = name.partition('/')
        return self._lookup._get_namespace(ns).module[fn_name]


class Lookup(object):

    def __init__(self, types, loader, cache=None, builtins=None):
        self.types = types
        self._loader = loader
        self._cache = cache or DictCache()
        self.builtins = builtins or {}
        self._namespaces = {}
        self._reqs = {}

    def _get_dependencies(self, ns, _visited=None):
        _visited = set([]) if _visited is None else _visited
        if ns.name not in _visited:
            _visited.add(ns.name)
            yield ns
            for dep_name in ns.dependencies:
                dep = self._namespaces[dep_name]
                for item in self._get_dependencies(dep, _visited=_visited):
                    yield item

    def _load_sources(self, name, _visited=None):
        _visited = set([]) if _visited is None else _visited
        if name not in _visited:
            _visited.add(name)
            source = self._loader.load(name)

            errors = Errors()
            try:
                with errors.module_ctx(name):
                    node = parse(list(tokenize(source.content, errors)), errors)
            except UserError as e:
                self._raise_on_errors(errors, type(e))
                raise

            node = NamesResolver(source.name).visit(node)
            dependencies = DependenciesVisitor.get_dependencies(node)
            yield ParsedSource(name, source.modified_time, node, dependencies)
            for dep in dependencies:
                for item in self._load_sources(dep, _visited=_visited):
                    yield item

    def _format_error(self, error):
        source = self._loader.load(error.func.module)
        source_lines = source.content.splitlines()

        start, end = error.location.start, error.location.end
        start_line, end_line = start.line - 1, end.line - 1

        first_line = source_lines[start_line]
        indent = len(first_line) - len(first_line.lstrip())
        indent = min(indent, start.column - 1)

        if end_line - start_line > 2:
            snippet = ['  | ' + source_lines[start_line][indent:],
                       ' ...',
                       '  | ' + source_lines[end_line][indent:]]
        elif end_line - start_line > 0:
            snippet = ['  | ' + source_lines[l][indent:]
                       for l in range(start_line, end_line + 1)]
        else:
            first_line_offset = sum(map(len, source_lines[:start_line])) + \
                                start_line
            highlight_indent = start.offset - first_line_offset - indent
            highlight_len = end.offset - start.offset
            highlight = (' ' * highlight_indent) + ('~' * highlight_len)
            snippet = ['  ' + source_lines[start_line][indent:],
                       '  ' + highlight]
        return (
            '{message}\n'
            '  File "{file}", line {line_num}, in {func_name}\n'
            '{snippet}'
            .format(
                message=error.message,
                file=source.file_path,
                line_num=start.line,
                func_name=error.func.name or '<content>',
                snippet='\n'.join('  ' + l for l in snippet),
            )
        )

    def _raise_on_errors(self, errors, error_cls=None):
        error_cls = UserError if error_cls is None else error_cls
        errors_list = []
        warnings_list = []
        for e in errors.list:
            msg = self._format_error(e)
            if e.severity == WARNING:
                warnings_list.append(msg)
            elif e.severity == ERROR:
                errors_list.append(msg)
            else:
                raise ValueError(repr(e.severity))

        if warnings_list:
            for msg in warnings_list:
                log.warn(msg)
        if errors_list:
            raise error_cls('\n'.join(errors_list))

    def _check(self, parsed_sources):
        env = dict(self.types)

        node = collect_defs(ps.node for ps in parsed_sources)
        env.update(def_types(node))

        environ = Environ(env)
        try:
            node = check(node, environ)
        except UserError as e:
            self._raise_on_errors(environ.errors, type(e))
        else:
            self._raise_on_errors(environ.errors)
        reqs = extract(node)

        modules = {ns: NamesUnResolver(ns).visit(mod)
                   for ns, mod in split_defs(node).items()}

        checked_sources = [ps._replace(node=modules[ps.name])
                           for ps in parsed_sources]

        return checked_sources, reqs

    def _compile_module(self, name, module):
        module_code = compile(module, '<{}.kinko>'.format(name), 'exec')
        globals_dict = {}
        _exec_in(module_code, globals_dict)
        return globals_dict

    def _load(self, name):
        ns = self._namespaces.get(name)
        if ns is not None:
            deps = list(self._get_dependencies(ns))
            if all(self._loader.is_uptodate(dep) for dep in deps):
                return

        parsed_sources = list(self._load_sources(name))
        checked_sources, refs = self._check(parsed_sources)

        modules = {cs.name: compile_module(cs.node) for cs in checked_sources}
        compiled_modules = {name: self._compile_module(name, module)
                            for name, module in modules.items()}

        for src in parsed_sources:
            self._namespaces[src.name] = Namespace(src.name, src.modified_time,
                                                   compiled_modules[src.name],
                                                   src.dependencies)
        self._reqs.update(refs)

    def _get_namespace(self, name):
        self._load(name)
        return self._namespaces[name]

    def _get_query(self, name):
        ns, _, _ = name.partition('/')
        self._load(ns)
        return self._reqs[name]

    def _render(self, name, result):
        ctx = Context(self, result)
        ctx.buffer.push()
        fn = ctx.lookup(name)
        fn(ctx)
        return ctx.buffer.pop()

    def get(self, name):
        return Function(self, name)
