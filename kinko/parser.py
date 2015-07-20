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


def parser():

    delim = lambda t: skip(token(Pattern(t)))

    symbol = token(Pattern(T.IDENT)) >> N.Symbol.from_token
    string = token(Pattern(T.STRING)) >> N.String.from_token
    placeholder = token(Pattern(T.PLACEHOLDER)) >> N.Placeholder.from_token
    keyword = token(Pattern(T.KEYWORD)) >> N.Keyword.from_token
    number = token(Pattern(T.NUMBER)) >> N.Number.from_token

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
