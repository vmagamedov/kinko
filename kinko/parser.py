from __future__ import absolute_import

from ast import literal_eval
from itertools import chain

from funcparserlib.parser import forward_decl, maybe, some, oneplus, Parser
from funcparserlib.parser import skip, many, NoParseError

from .nodes import Symbol, String, Placeholder, Keyword, Number, List
from .nodes import Dict, Tuple
from .sugar import InterpolateString, TranslateDots
from .errors import UserError, Errors
from .tokenizer import Token, Location, Position


IMPLICIT_TUPLE_ERROR = 'Invalid function call'
EXPLICIT_TUPLE_ERROR = 'Invalid tuple literal'
DICT_ERROR = 'Invalid Dict literal'


class ParseError(UserError):
    pass


class LastError(object):

    def __init__(self):
        self._pos = -1
        self._explanation = None

    def push(self, position, explanation):
        if position > self._pos:
            self._pos = position
            self._explanation = explanation

    def pop(self, default):
        return self._explanation or default


def error_ctx(p, last_error, message):
    @Parser
    def wrapper(tokens, s):
        try:
            (v, s2) = p.run(tokens, s)
        except NoParseError as e:
            last_error.push(e.state.max, message)
            raise
        return v, s2
    return wrapper


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


def _list(open_br, values, close_br):
    return List(values, location=Location(open_br.location.start,
                                          close_br.location.end))


def _dict(open_br, pairs, close_br):
    return Dict(chain.from_iterable(pairs),
                location=Location(open_br.location.start,
                                  close_br.location.end))


def _tuple(open_par, sym, args, close_par):
    return Tuple([sym] + args, location=Location(open_par.location.start,
                                                 close_par.location.end))


def _implicit_tuple(sym, inline_args, indented_args):
    start_pos = sym.location.start
    if indented_args:
        end_pos = indented_args[-1].location.end
    elif inline_args:
        end_pos = inline_args[-1].location.end
    else:
        end_pos = sym.location.end
    return Tuple([sym] + inline_args + (indented_args or []),
                 location=Location(start_pos, end_pos))


def _maybe_join(values):
    if len(values) == 1:
        return values[0]
    else:
        start_loc = Location(values[0].location.start, values[0].location.start)
        range_loc = Location(values[0].location.start, values[-1].location.end)
        return Tuple([Symbol('join', location=start_loc),
                      List(values, location=range_loc)],
                     location=range_loc)


def _module(values, eof):
    return List(values, location=Location(Position(0, 0, 0), eof.location.end))


def parser(last_error=None):
    last_error = LastError() if last_error is None else last_error

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

    list_ = (
        (_tok(Token.OPEN_BRACKET) +
         many(expr | keyword) +
         _tok(Token.CLOSE_BRACKET)) >>
        apl(_list)
    )

    dict_ = (
        error_ctx(_tok(Token.OPEN_BRACE) +
                  many(keyword + expr) +
                  _tok(Token.CLOSE_BRACE),
                  last_error,
                  DICT_ERROR) >>
        apl(_dict)
    )

    inline_args = many(expr | keyword)

    explicit_tuple = (
        error_ctx(_tok(Token.OPEN_PAREN) +
                  symbol + inline_args +
                  _tok(Token.CLOSE_PAREN),
                  last_error,
                  EXPLICIT_TUPLE_ERROR) >>
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
        error_ctx(symbol + inline_args + delim(Token.NEWLINE) +
                  maybe(delim(Token.INDENT) +
                        indented_args_kwargs +
                        delim(Token.DEDENT)),
                  last_error,
                  IMPLICIT_TUPLE_ERROR) >>
        apl(_implicit_tuple)
    )

    expr.define(symbol | string | number | explicit_tuple | list_ | dict_ |
                placeholder)

    body = (
        (many(implicit_tuple) + _tok(Token.EOF)) >>
        apl(_module)
    )
    return body


def parse(tokens, errors=None):
    errors = Errors() if errors is None else errors
    last_error = LastError()
    try:
        node = parser(last_error).parse(tokens)
    except NoParseError as e:
        msg = last_error.pop('Syntax error')
        if len(tokens) > e.state.max:
            token = tokens[e.state.max]
        else:
            token = tokens[-1]
        with errors.location(token.location):
            raise ParseError('{}; unexpected token "{}"'
                             .format(msg, token.type))
    else:
        node = InterpolateString().visit(node)
        node = TranslateDots().visit(node)
        return node
