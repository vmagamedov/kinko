from __future__ import absolute_import

from ast import literal_eval
from itertools import chain

from funcparserlib.parser import forward_decl, maybe, some, oneplus
from funcparserlib.parser import skip, many

from .nodes import Symbol, String, Placeholder, Keyword, Number, List
from .nodes import Dict, Tuple
from .sugar import InterpolateString, TranslateDots
from .tokenizer import Token, Location, Position


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


def _list(open_br, values):
    return List(values, location=open_br.location)


def _dict(open_br, pairs):
    return Dict(chain.from_iterable(pairs), location=open_br.location)


def _tuple(open_par, sym, args):
    return Tuple([sym] + args, location=open_par.location)


def _implicit_tuple(sym, inline_args, indented_args):
    return Tuple([sym] + inline_args + (indented_args or []),
                 location=sym.location)


def _maybe_join(values):
    if len(values) == 1:
        return values[0]
    else:
        return Tuple([Symbol('join', location=values[0].location),
                      List(values, location=values[0].location)],
                     location=values[0].location)


def _module(values, eof):
    return List(values, location=Location(Position(0, 0, 0), eof.location.end))


def parser():
    def apl(f):
        return lambda x: f(*x)

    def delim(t):
        return skip(_tok(t))

    symbol = _tok(Token.SYMBOL) >> _gen(Symbol)
    string = _tok(Token.STRING) >> _gen(String)
    placeholder = _tok(Token.PLACEHOLDER) >> _gen(Placeholder)
    keyword = _tok(Token.KEYWORD) >> _gen(Keyword)

    # Note: tokenizer guarantee that value consists of dots and digits
    # TODO: convert exceptions
    number = _tok(Token.NUMBER) >> _gen(Number, literal_eval)

    expr = forward_decl()
    implicit_tuple = forward_decl()

    list_ = ((_tok(Token.OPEN_BRACKET) +
              many(expr | keyword) +
              delim(Token.CLOSE_BRACKET)) >>
             apl(_list))

    dict_ = ((_tok(Token.OPEN_BRACE) +
              many(keyword + expr) +
              delim(Token.CLOSE_BRACE)) >>
             apl(_dict))

    inline_args = many(expr | keyword)

    explicit_tuple = (
        (_tok(Token.OPEN_PAREN) +
         symbol + inline_args +
         delim(Token.CLOSE_PAREN)) >>
        apl(_tuple)
    )

    indented_arg = (
        oneplus(implicit_tuple | expr + delim(Token.NEWLINE)) >>
        _maybe_join
    )

    indented_kwarg = (
        ((keyword + expr + delim(Token.NEWLINE)) |
         (keyword + delim(Token.NEWLINE) +
          delim(Token.INDENT) + indented_arg + delim(Token.DEDENT)))
    )

    indented_args_kwargs = (
        (many(indented_kwarg) + many(indented_arg)) >>
        apl(lambda pairs, args: list(chain(*(pairs + [args]))))
    )

    implicit_tuple.define(
        (symbol + inline_args + delim(Token.NEWLINE) +
         maybe(delim(Token.INDENT) +
               indented_args_kwargs +
               delim(Token.DEDENT))) >>
        apl(_implicit_tuple)
    )

    expr.define(symbol | string | number | explicit_tuple | list_ | dict_ |
                placeholder)

    body = (
        (many(implicit_tuple) + _tok(Token.EOF)) >>
        apl(_module)
    )
    return body


def parse(tokens):
    node = parser().parse(tokens)
    node = InterpolateString().visit(node)
    node = TranslateDots().visit(node)
    return node
