from textwrap import dedent
from collections import namedtuple

import pytest

from kinko.errors import Errors
from kinko.tokenizer import tokenize as _tokenize
from kinko.tokenizer import Token, TokenizerError


NL = (Token.NEWLINE, '\n')

EOF = (Token.EOF, '')


def tokenize(src, errors=None):
    src = dedent(src).strip()
    return _tokenize(src, errors)


def check_tokens(string, tokens):
    left = [(kind, value) for (kind, value, loc) in tokenize(string)]
    assert left == tokens


def check_errors(string, messages):
    errors = Errors()
    try:
        list(tokenize(string, errors))
    except TokenizerError:
        errors_set = {
            (e.message, e.location.start.offset, e.location.end.offset)
            for e in errors.list
        }
        for error in messages:
            assert error in errors_set
    else:
        raise AssertionError('No errors')


def test_symbol():
    check_tokens(
        'a foo1 foo.bar foo-bar foo/bar ./foo foo_bar Foo',
        [
            (Token.SYMBOL, 'a'),
            (Token.SYMBOL, 'foo1'),
            (Token.SYMBOL, 'foo.bar'),
            (Token.SYMBOL, 'foo-bar'),
            (Token.SYMBOL, 'foo/bar'),
            (Token.SYMBOL, './foo'),
            (Token.SYMBOL, 'foo_bar'),
            (Token.SYMBOL, 'Foo'), NL,
            EOF,
        ],
    )


def test_string():
    check_tokens(
        '"foo" "foo.bar" "foo-bar" "foo/bar" "foo_bar" "Foo" '
        '":foo" "#foo" "{}" "[]" "()" "123"',
        [
            (Token.STRING, 'foo'),
            (Token.STRING, 'foo.bar'),
            (Token.STRING, 'foo-bar'),
            (Token.STRING, 'foo/bar'),
            (Token.STRING, 'foo_bar'),
            (Token.STRING, 'Foo'),
            (Token.STRING, ':foo'),
            (Token.STRING, '#foo'),
            (Token.STRING, '{}'),
            (Token.STRING, '[]'),
            (Token.STRING, '()'),
            (Token.STRING, '123'), NL,
            EOF,
        ],
    )


def test_number():
    check_tokens(
        '1 2.3 4.5d 6d.7 8d 9...',
        [
            (Token.NUMBER, '1'),
            (Token.NUMBER, '2.3'),
            (Token.NUMBER, '4.5d'),
            (Token.NUMBER, '6d.7'),
            (Token.NUMBER, '8d'),
            (Token.NUMBER, '9...'), NL,
            EOF,
        ],
    )


def test_keyword():
    check_tokens(
        ':foo :foo-bar :foo_bar',
        [
            (Token.KEYWORD, 'foo'),
            (Token.KEYWORD, 'foo-bar'),
            (Token.KEYWORD, 'foo_bar'), NL,
            EOF,
        ],
    )


def test_placeholder():
    check_tokens(
        '#foo #foo-bar #foo_bar #foo.bar',
        [
            (Token.PLACEHOLDER, 'foo'),
            (Token.PLACEHOLDER, 'foo-bar'),
            (Token.PLACEHOLDER, 'foo_bar'),
            (Token.PLACEHOLDER, 'foo.bar'), NL,
            EOF,
        ],
    )


def test_brackets():
    check_tokens(
        'foo (bar [baz {:key "value"} "text"] 1)',
        [
            (Token.SYMBOL, 'foo'),
            (Token.OPEN_PAREN, '('),
            (Token.SYMBOL, 'bar'),
            (Token.OPEN_BRACKET, '['),
            (Token.SYMBOL, 'baz'),
            (Token.OPEN_BRACE, '{'),
            (Token.KEYWORD, 'key'),
            (Token.STRING, 'value'),
            (Token.CLOSE_BRACE, '}'),
            (Token.STRING, 'text'),
            (Token.CLOSE_BRACKET, ']'),
            (Token.NUMBER, '1'),
            (Token.CLOSE_PAREN, ')'), NL,
            EOF,
        ],
    )


def test_indent():
    check_tokens(
        """
        s1
          s11
            s111
          s12
          s13
            s112
        """,
        [
            (Token.SYMBOL, 's1'), NL,
            (Token.INDENT, ''),
            (Token.SYMBOL, 's11'), NL,
            (Token.INDENT, ''),
            (Token.SYMBOL, 's111'), NL,
            (Token.DEDENT, ''),
            (Token.SYMBOL, 's12'), NL,
            (Token.SYMBOL, 's13'), NL,
            (Token.INDENT, ''),
            (Token.SYMBOL, 's112'), NL,
            (Token.DEDENT, ''),
            (Token.DEDENT, ''),
            EOF,
        ]
    )


def test_comments():
    check_tokens(
        """
        ; comment
        ; :foo
        ; #foo
        ; {} [] ()
        foo
          bar ; comment
        """,
        [
            (Token.SYMBOL, 'foo'), NL,
            (Token.INDENT, ''),
            (Token.SYMBOL, 'bar'), NL,
            (Token.DEDENT, ''),
            EOF,
        ],
    )


Msg = namedtuple('msg', 'text start end')


def test_invalid_character_error():
    src = 'foo ` bar'
    msg = Msg("Wrong character '`'", 4, 5)
    check_errors(src, [msg])
    assert src[msg.start:msg.end] == '`'


def test_incomplete_string():
    src = '"foo'
    msg = Msg('String does not and at EOF', 0, 4)
    check_errors(src, [msg])
    assert src[msg.start:msg.end] == '"foo'


def test_string_with_newline():
    src = '"foo\nbar"'
    msg = Msg('Newlines are not allowed in strings', 0, 5)
    check_errors(src, [msg])
    assert src[msg.start:msg.end] == '"foo\n'


@pytest.mark.parametrize('bracket', '[({')
def test_incomplete_parentheses(bracket):
    src = 'foo {}bar'.format(bracket)
    msg = Msg('Not closed parenthesis', 4, 8)
    check_errors(src, [msg])
    assert src[msg.start:msg.end] == '{}bar'.format(bracket)


@pytest.mark.parametrize(
    ['open_br', 'closing_br', 'invalid_br'],
    [(a, b, c) for a, b in zip('[({', '])}') for c in '])}' if b != c]
)
def test_invalid_parentheses(open_br, closing_br, invalid_br):
    src = 'foo {}bar{}'.format(open_br, invalid_br)
    msg = Msg(
        "Unmatching parenthesis, expected '{}' got '{}'"
        .format(closing_br, invalid_br),
        4, 9,
    )
    check_errors(src, [msg])
    assert src[msg.start:msg.end] == '{}bar{}'.format(open_br, invalid_br)


@pytest.mark.parametrize('bracket', '])}')
def test_unknown_parentheses(bracket):
    src = 'foo bar{}'.format(bracket)
    msg = Msg("No parenthesis matching '{}'".format(bracket), 7, 8)
    check_errors(src, [msg])
    assert src[msg.start:msg.end] == bracket


def test_indent_with_tabs():
    src = 'foo\n\tbar'
    msg = Msg('Please indent by spaces', 4, 5)
    check_errors(src, [msg])
    assert src[msg.start:msg.end] == '\t'


def test_invalid_dedent():
    src = 'a\n  b\n    c\n   d\ne'
    msg = Msg('Indentation level mismatch', 12, 15)
    check_errors(src, [msg])
    assert src[msg.start:msg.end + 1] == '   d'
