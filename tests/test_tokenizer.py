from textwrap import dedent

import pytest

from kinko.errors import Errors
from kinko.tokenizer import tokenize as _tokenize
from kinko.tokenizer import Token, TokenizerError


NL = (Token.NEWLINE, '\n')

EOF = (Token.EOF, '')


def tokenize(src, errors=None):
    src = dedent(src).strip() + '\n'
    return _tokenize(src, errors)


def check_tokens(string, tokens):
    left = [(kind, value) for (kind, value, loc) in tokenize(string)]
    assert left == tokens


def check_errors(string, messages):
    errors = Errors()
    try:
        list(tokenize(string, errors))
    except TokenizerError:
        errors_map = {e.message for e in errors.list}
        assert errors_map == set(messages)
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


def test_laceholder():
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


@pytest.mark.parametrize('bracket', '[({')
def test_incomplete_parentheses(bracket):
    check_errors(
        """
        foo {}bar
        """.format(bracket),
        ['Not closed parenthesis'],
    )


@pytest.mark.parametrize(
    ['open_br', 'closing_br', 'invalid_br'],
    [(a, b, c) for a, b in zip('[({', '])}') for c in '])}' if b != c]
)
def test_invalid_parentheses(open_br, closing_br, invalid_br):
    check_errors(
        """
        foo {}bar{}
        """.format(open_br, invalid_br),
        ["Unmatching parenthesis, expected '{}' got '{}'"
         .format(closing_br, invalid_br)],
    )


@pytest.mark.parametrize('bracket', '])}')
def test_unknown_parentheses(bracket):
    check_errors(
        """
        foo bar{}
        """.format(bracket),
        ["No parenthesis matching '{}'".format(bracket)],
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


def test_indent_with_tabs():
    check_errors(
        """
        a
        \tb
        """,
        ['Please indent by spaces'],
    )


def test_invalid_dedent():
    check_errors(
        """
        a
          b
         c
        """,
        ['Indentation level mismatch'],
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
