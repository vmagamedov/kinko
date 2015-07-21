from __future__ import absolute_import

from ast import literal_eval

from funcparserlib.parser import a as token, forward_decl, maybe
from funcparserlib.parser import skip, many
from .tokenizer import Token as T
from . import nodes as N


class Pattern(object):
    def __init__(self, kind, value=None):
        self.kind = kind
        self.value = value

    def __eq__(self, other):
        assert isinstance(other, tuple), other
        assert len(other) == 3, other
        kind, value, location = other
        if self.kind != kind:
            return False
        if self.value is None:
            return True
        return self.value == value


def node_gen(node_cls, coerce=None):
    if coerce is None:
        def proc(token):
            _, value, location = token
            return node_cls(value, location=location)
    else:
        def proc(token):
            _, value, location = token
            value = coerce(value)
            return node_cls(value, location=location)
    return proc


def parser():

    delim = lambda t: skip(token(Pattern(t)))

    symbol = token(Pattern(T.IDENT)) >> node_gen(N.Symbol)

    # Note: tokenizer guarantee that value is always quoted string
    string = token(Pattern(T.STRING)) >> node_gen(N.String, literal_eval)

    placeholder = token(Pattern(T.PLACEHOLDER)) >> node_gen(N.Placeholder)
    keyword = token(Pattern(T.KEYWORD)) >> node_gen(N.Keyword)

    # Note: tokenizer guarantee that value consists of dots and digits
    # TODO(tailhook) convert exceptions
    number = token(Pattern(T.NUMBER)) >> node_gen(N.Number, literal_eval)

    expr = forward_decl()
    tuple_ = forward_decl()

    dotname = symbol + many(delim(T.DOT) + symbol) \
        >> (lambda t: N.Dotname(*t))
    list_ = (delim(T.OPEN_BRACKET) + many(expr) +
             delim(T.CLOSE_BRACKET)) >> N.List
    dict_ = (delim(T.OPEN_BRACE) +
        many(keyword + expr) +
        delim(T.CLOSE_BRACE)) >> N.Dict
    inline_keyword = keyword + expr >> (lambda t: N.KeywordPair(*t))
    block_keyword = ((keyword + expr + delim(T.NEWLINE)) |
        (keyword + delim(T.NEWLINE) +
         delim(T.INDENT) + many(tuple_) + delim(T.DEDENT))
         ) >> (lambda t: N.KeywordPair(*t))

    paren_tuple = (delim(T.OPEN_PAREN) +
        symbol + many(expr) +
        delim(T.CLOSE_PAREN)) >> (lambda pair: N.Tuple(*pair))
    tuple_.define(
        (symbol + many(expr | inline_keyword) + delim(T.NEWLINE) +
        maybe(delim(T.INDENT) +
            many(tuple_|placeholder|block_keyword |
                ((string|number) + delim(T.NEWLINE))) +
            delim(T.DEDENT)))
        >> (lambda triple: N.Tuple(triple[0], triple[1]+(triple[2] or []))))
    expr.define(dotname | paren_tuple | string | number | dict_ | list_ |
        placeholder)

    body = many(tuple_) + delim(T.EOF)

    return body
