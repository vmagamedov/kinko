from __future__ import absolute_import

from ast import literal_eval

from funcparserlib.parser import forward_decl, maybe, some
from funcparserlib.parser import skip, many

from .nodes import Symbol, String, Placeholder, Keyword, Number, List
from .nodes import Dict, KeywordPair, Tuple, Dotname
from .tokenizer import Token


def node_gen(node_cls, coerce_=None):
    if coerce_ is None:
        def proc(token):
            _, value, location = token
            return node_cls(value, location=location)
    else:
        def proc(token):
            _, value, location = token
            value = coerce_(value)
            return node_cls(value, location=location)
    return proc


def tok(type_):
    def pred(t):
        return t.type == type_
    return some(pred).named(u'(a "{}")'.format(type_))


def parser():

    delim = lambda t: skip(tok(t))

    symbol = tok(Token.SYMBOL) >> node_gen(Symbol)

    # Note: tokenizer guarantee that value is always quoted string
    string = tok(Token.STRING) >> node_gen(String)

    placeholder = tok(Token.PLACEHOLDER) >> node_gen(Placeholder)
    keyword = tok(Token.KEYWORD) >> node_gen(Keyword)

    # Note: tokenizer guarantee that value consists of dots and digits
    # TODO(tailhook) convert exceptions
    number = tok(Token.NUMBER) >> node_gen(Number, literal_eval)

    expr = forward_decl()
    tuple_ = forward_decl()

    dotname = symbol + many(delim(Token.DOT) + symbol) \
        >> (lambda t: Dotname(*t))
    list_ = (delim(Token.OPEN_BRACKET) + many(expr) +
             delim(Token.CLOSE_BRACKET)) >> List
    dict_ = (delim(Token.OPEN_BRACE) +
        many(keyword + expr) +
        delim(Token.CLOSE_BRACE)) >> Dict
    inline_keyword = keyword + expr >> (lambda t: KeywordPair(*t))
    block_keyword = ((keyword + expr + delim(Token.NEWLINE)) |
        (keyword + delim(Token.NEWLINE) +
         delim(Token.INDENT) + many(tuple_) + delim(Token.DEDENT))
         ) >> (lambda t: KeywordPair(*t))

    paren_tuple = (delim(Token.OPEN_PAREN) +
        symbol + many(expr) +
        delim(Token.CLOSE_PAREN)) >> (lambda pair: Tuple(*pair))
    tuple_.define(
        (symbol + many(expr | inline_keyword) + delim(Token.NEWLINE) +
        maybe(delim(Token.INDENT) +
            many(tuple_|placeholder|block_keyword |
                ((string|number) + delim(Token.NEWLINE))) +
            delim(Token.DEDENT)))
        >> (lambda triple: Tuple(triple[0], triple[1]+(triple[2] or []))))
    expr.define(dotname | paren_tuple | string | number | dict_ | list_ |
        placeholder)

    body = many(tuple_) + delim(Token.EOF)

    return body
