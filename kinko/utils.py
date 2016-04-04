import io
from contextlib import contextmanager
from collections import Counter

from markupsafe import Markup, escape

from .nodes import Keyword
from .types import TypeVar, NamedArgMeta, VarArgsMeta, VarNamedArgsMeta
from .compat import text_type


class Buffer(object):

    def __init__(self):
        self.stack = []

    def write(self, s):
        self.stack[-1].write(text_type(s))

    def write_unsafe(self, s):
        self.stack[-1].write(escape(s))

    def push(self):
        self.stack.append(io.StringIO())

    def pop(self):
        return Markup(self.stack.pop().getvalue())


class VarsGen(object):

    def __init__(self):
        self.vars = {}

    def __getattr__(self, name):
        if name not in self.vars:
            self.vars[name] = TypeVar[None]
        return self.vars[name]


def split_args(args):
    _pos_args, _kw_args = [], {}
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
                    _kw_args[arg.name] = val
            else:
                _pos_args.append(arg)
    except StopIteration:
        return _pos_args, _kw_args


def normalize_args(fn_type, pos_args, kw_args):
    pos_args, kw_args = list(pos_args), dict(kw_args)
    norm_args = []
    missing_arg = False
    for arg_type in fn_type.__args__:
        if isinstance(arg_type, NamedArgMeta):
            try:
                value = kw_args.pop(arg_type.__arg_name__)
            except KeyError:
                missing_arg = True
                break
            else:
                norm_args.append(value)
        elif isinstance(arg_type, VarArgsMeta):
            norm_args.append(list(pos_args))
            del pos_args[:]
        elif isinstance(arg_type, VarNamedArgsMeta):
            norm_args.append(kw_args.copy())
            kw_args.clear()
        else:
            try:
                value = pos_args.pop(0)
            except IndexError:
                missing_arg = True
                break
            else:
                norm_args.append(value)
    if pos_args or kw_args or missing_arg:
        raise TypeError('Signature mismatch')
    else:
        return norm_args


class Environ(object):

    def __init__(self):
        self.vars = Counter()

    def __getitem__(self, key):
        i = self.vars[key]
        return '{}_{}'.format(key, i) if i > 1 else key

    def __contains__(self, key):
        return key in self.vars

    @contextmanager
    def push(self, names):
        for name in names:
            self.vars[name] += 1
        try:
            yield
        finally:
            for name in names:
                self.vars[name] -= 1
