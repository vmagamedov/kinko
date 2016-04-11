from contextlib import contextmanager
from json.encoder import encode_basestring

from .nodes import Tuple, Symbol, Placeholder, String, Keyword
from .nodes import NodeVisitor, NodeTransformer
from .compat import text_type


def _indent_needed(arg):
    if isinstance(arg, Tuple) and arg.values[0].name != 'get':
        return True
    elif isinstance(arg, String) and len(arg.value) > 50:
        return True
    else:
        return False


def _brake_args(args):
    inline_kwargs, inline_args, indented_kwargs, indented_arg = [], [], [], None
    i = iter(args)
    try:
        while True:
            arg = next(i)
            if isinstance(arg, Keyword):
                try:
                    val = next(i)
                except StopIteration:
                    raise TypeError('Missing named argument value')
                else:
                    if _indent_needed(val):
                        indented_kwargs.append((arg, val))
                    else:
                        inline_kwargs.append((arg, val))
            else:
                if _indent_needed(arg) and indented_arg is None:
                    indented_arg = arg
                elif _indent_needed(arg) and indented_arg is not None:
                    raise ValueError('Already have one indented arg')
                else:
                    inline_args.append(arg)
    except StopIteration:
        return inline_kwargs, inline_args, indented_kwargs, indented_arg


class InlinePrinter(NodeTransformer):

    def visit_symbol(self, node):
        return node.name

    def visit_number(self, node):
        return text_type(node.value)

    def visit_string(self, node):
        return encode_basestring(node.value)

    def visit_keyword(self, node):
        return ':{}'.format(node.name)

    def visit_placeholder(self, node):
        return '#{}'.format(node.name)

    def visit_tuple(self, node):
        sym, args = node.values[0], node.values[1:]
        if sym.name == 'get':
            obj, name = args
            if isinstance(obj, Symbol):
                return self.visit(Symbol('{}.{}'.format(obj.name,
                                                        name.name)))
            elif isinstance(obj, Placeholder):
                return self.visit(Placeholder('{}.{}'.format(obj.name,
                                                             name.name)))
        return '(' + ' '.join(self.visit(v) for v in node.values) + ')'

    def visit_list(self, node):
        return '[' + ' '.join(self.visit(v) for v in node.values) + ']'

    def visit_dict(self, node):
        return '{' + ' '.join(self.visit(v) for v in node.values) + '}'


class Printer(NodeVisitor):

    def __init__(self):
        self._buffer = []
        self._indent_size = 2
        self._indent_count = 0
        self._inline_printer = InlinePrinter()

    @classmethod
    def dumps(cls, node):
        printer = cls()
        printer.visit(node)
        return '\n'.join(printer._buffer) + '\n'

    @contextmanager
    def _indent(self):
        self._indent_count += 1
        try:
            yield
        finally:
            self._indent_count -= 1

    def _newline(self):
        self._buffer.append('')

    def _print(self, line):
        self._buffer.append((' ' * self._indent_size * self._indent_count) +
                            line)

    def _append(self, string):
        self._buffer[-1] += ' ' + string

    def visit_tuple(self, node):
        sym, args = node.values[0], node.values[1:]

        if sym.name == 'join':
            body, = args
            for item in body.values:
                self.visit(item)
            return

        self._print(sym.name)
        inline_kwargs, inline_args, indented_kwargs, indented_arg = \
            _brake_args(args)
        for key, value in inline_kwargs:
            self._append(self._inline_printer.visit(key))
            self._append(self._inline_printer.visit(value))
        for arg in inline_args:
            self._append(self._inline_printer.visit(arg))

        with self._indent():
            for key, value in indented_kwargs:
                self.visit(key)
                with self._indent():
                    self.visit(value)
            if indented_arg is not None:
                self.visit(indented_arg)

        if sym.name == 'def':
            self._newline()

    def visit_string(self, node):
        self._print(self._inline_printer.visit(node))

    def visit_keyword(self, node):
        self._print(self._inline_printer.visit(node))
