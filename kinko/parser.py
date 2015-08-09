from __future__ import absolute_import

from ast import literal_eval
from functools import partial
from itertools import chain
try:
    from functools import reduce
except ImportError:
    pass

from funcparserlib.parser import forward_decl, maybe, some, oneplus
from funcparserlib.parser import skip, many

from .nodes import Symbol, String, Placeholder, Keyword, Number, List
from .nodes import Dict, Tuple
from .tokenizer import Token


def _tok(type_):
    def pred(t):
        return t.type == type_
    return some(pred).named(u'(a "{}")'.format(type_))


def _gen(node_cls, coerce_=None):
    if coerce_ is None:
        def proc(token):
            return node_cls(token.value, location=token.location)
    else:
        def proc(token):
            return node_cls(coerce_(token.value), location=token.location)
    return proc


def _dotted(node_cls):
    def gen(token):
        # TODO: validate token value
        sym = partial(Symbol, location=token.location)
        parts = token.value.split('.')
        head, tail = parts[0], parts[1:]
        return reduce(lambda value, attr: Tuple([sym('get'), value, sym(attr)]),
                      tail, node_cls(head, location=token.location))
    return gen


_as_list = lambda x: x >> (lambda y: [y])


def parser():
    delim = lambda t: skip(_tok(t))

    symbol = _tok(Token.SYMBOL) >> _dotted(Symbol)
    string = _tok(Token.STRING) >> _gen(String)
    placeholder = _tok(Token.PLACEHOLDER) >> _dotted(Placeholder)
    keyword = _tok(Token.KEYWORD) >> _gen(Keyword)

    # Note: tokenizer guarantee that value consists of dots and digits
    # TODO: convert exceptions
    number = _tok(Token.NUMBER) >> _gen(Number, literal_eval)

    expr = forward_decl()
    implicit_tuple = forward_decl()

    list_ = ((delim(Token.OPEN_BRACKET) +
              many(expr | keyword) +
              delim(Token.CLOSE_BRACKET))
             >> (lambda x: List(x)))

    dict_ = ((delim(Token.OPEN_BRACE) +
              many(keyword + expr) +
              delim(Token.CLOSE_BRACE))
             >> (lambda x: Dict(chain(*x))))

    inline_args = many(expr | keyword)

    explicit_tuple = (
        (delim(Token.OPEN_PAREN) +
         symbol + inline_args +
         delim(Token.CLOSE_PAREN))
        >> (lambda x: Tuple([x[0]] + x[1]))
    )

    indented_arg = (
        oneplus(implicit_tuple | expr + delim(Token.NEWLINE))
        >> (lambda x:
            x[0] if len(x) == 1 else Tuple([Symbol('join'), List(x)]))
    )

    indented_kwarg = (
        ((keyword + expr + delim(Token.NEWLINE)) |
         (keyword + delim(Token.NEWLINE) +
          delim(Token.INDENT) + indented_arg + delim(Token.DEDENT)))
        >> (lambda x: tuple(x))
    )

    indented_kwargs = (
        oneplus(indented_kwarg)
        >> (lambda x: list(chain(*x)))
    )

    implicit_tuple.define(
        (symbol + inline_args + delim(Token.NEWLINE) +
         maybe(delim(Token.INDENT) +
               (_as_list(indented_arg) | indented_kwargs) +
               delim(Token.DEDENT)))
        >> (lambda x: Tuple([x[0]] + x[1] + (x[2] or [])))
    )

    expr.define(symbol | string | number | explicit_tuple | list_ | dict_ |
                placeholder)

    body = (
        (many(implicit_tuple) + delim(Token.EOF))
        >> (lambda x: List(x))
    )
    return body
