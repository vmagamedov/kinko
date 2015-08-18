import cgi
import sys
import json
import codecs
import traceback

from .utils import Buffer
from .compat import _exec_in
from .parser import parser
from .compiler import compile_module
from .tokenizer import tokenize


try:
    _, src_file, func_name, ctx_file, out_file = sys.argv
except ValueError:
    print("Usage: python -m kinko SRCFILE FUNCNAME CTXFILE OUTFILE")
    sys.exit(1)


class Object(dict):

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError('Unknown context variable: {}'.format(name))


with codecs.open(src_file, encoding='utf-8') as f:
    src = f.read()

with codecs.open(ctx_file, encoding='utf-8') as f:
    ctx = json.loads(f.read(), object_hook=Object)

try:
    tokens = list(tokenize(src))
    mod = compile_module(parser().parse(tokens))
    mod_code = compile(mod, '<kinko-template>', 'exec')

    buf = Buffer()
    buf.push()
    ns = {'buf': buf, 'ctx': ctx, 'builtins': object()}
    _exec_in(mod_code, ns)
    ns[func_name]()
    output = buf.pop()
except Exception:
    output = (
        "<html><head></head><body><pre>{tb}</pre></body></html>"
        .format(tb=cgi.escape(traceback.format_exc()))
    )
    raise
finally:
    with codecs.open(out_file, 'wb+', encoding='utf-8') as f:
        f.write(output)
