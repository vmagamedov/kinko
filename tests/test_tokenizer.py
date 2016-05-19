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


def check_tokens(string, reference):
    string = dedent(string).strip()
    values = [
        (kind, value, loc.start.offset, loc.end.offset,
         string[loc.start.offset:loc.end.offset])
        for kind, value, loc in tokenize(string)
    ]
    assert values == reference
    last_pos = len(string)
    assert values[-1][2:4] == (last_pos, last_pos)  # EOF


def check_errors(string, messages):
    errors = Errors()
    try:
        list(_tokenize(string, errors))
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
            (Token.SYMBOL, 'a', 0, 1, 'a'),
            (Token.SYMBOL, 'foo1', 2, 6, 'foo1'),
            (Token.SYMBOL, 'foo.bar', 7, 14, 'foo.bar'),
            (Token.SYMBOL, 'foo-bar', 15, 22, 'foo-bar'),
            (Token.SYMBOL, 'foo/bar', 23, 30, 'foo/bar'),
            (Token.SYMBOL, './foo', 31, 36, './foo'),
            (Token.SYMBOL, 'foo_bar', 37, 44, 'foo_bar'),
            (Token.SYMBOL, 'Foo', 45, 48, 'Foo'),
            (Token.NEWLINE, '\n', 48, 48, ''),
            (Token.EOF, '', 48, 48, ''),
        ],
    )


def test_string():
    check_tokens(
        '"foo" "foo.bar" "foo-bar" "foo/bar" "foo_bar" "Foo" '
        '":foo" "#foo" "{}" "[]" "()" "123"',
        [
            (Token.STRING, 'foo', 0, 5, '"foo"'),
            (Token.STRING, 'foo.bar', 6, 15, '"foo.bar"'),
            (Token.STRING, 'foo-bar', 16, 25, '"foo-bar"'),
            (Token.STRING, 'foo/bar', 26, 35, '"foo/bar"'),
            (Token.STRING, 'foo_bar', 36, 45, '"foo_bar"'),
            (Token.STRING, 'Foo', 46, 51, '"Foo"'),
            (Token.STRING, ':foo', 52, 58, '":foo"'),
            (Token.STRING, '#foo', 59, 65, '"#foo"'),
            (Token.STRING, '{}', 66, 70, '"{}"'),
            (Token.STRING, '[]', 71, 75, '"[]"'),
            (Token.STRING, '()', 76, 80, '"()"'),
            (Token.STRING, '123', 81, 86, '"123"'),
            (Token.NEWLINE, '\n', 86, 86, ''),
            (Token.EOF, '', 86, 86, ''),
        ],
    )


def test_number():
    check_tokens(
        '1 2.3 4.5d 6d.7 8d 9...',
        [
            (Token.NUMBER, '1', 0, 1, '1'),
            (Token.NUMBER, '2.3', 2, 5, '2.3'),
            (Token.NUMBER, '4.5d', 6, 10, '4.5d'),
            (Token.NUMBER, '6d.7', 11, 15, '6d.7'),
            (Token.NUMBER, '8d', 16, 18, '8d'),
            (Token.NUMBER, '9...', 19, 23, '9...'),
            (Token.NEWLINE, '\n', 23, 23, ''),
            (Token.EOF, '', 23, 23, ''),
        ],
    )


def test_keyword():
    check_tokens(
        ':foo :foo-bar :foo_bar',
        [
            (Token.KEYWORD, 'foo', 0, 4, ':foo'),
            (Token.KEYWORD, 'foo-bar', 5, 13, ':foo-bar'),
            (Token.KEYWORD, 'foo_bar', 14, 22, ':foo_bar'),
            (Token.NEWLINE, '\n', 22, 22, ''),
            (Token.EOF, '', 22, 22, ''),
        ],
    )


def test_placeholder():
    check_tokens(
        '#foo #foo-bar #foo_bar #foo.bar',
        [
            (Token.PLACEHOLDER, 'foo', 0, 4, '#foo'),
            (Token.PLACEHOLDER, 'foo-bar', 5, 13, '#foo-bar'),
            (Token.PLACEHOLDER, 'foo_bar', 14, 22, '#foo_bar'),
            (Token.PLACEHOLDER, 'foo.bar', 23, 31, '#foo.bar'),
            (Token.NEWLINE, '\n', 31, 31, ''),
            (Token.EOF, '', 31, 31, ''),
        ],
    )


def test_brackets():
    check_tokens(
        'foo (bar [baz {:key "value"} "text"] 1)',
        [
            (Token.SYMBOL, 'foo', 0, 3, 'foo'),
            (Token.OPEN_PAREN, '(', 4, 5, '('),
            (Token.SYMBOL, 'bar', 5, 8, 'bar'),
            (Token.OPEN_BRACKET, '[', 9, 10, '['),
            (Token.SYMBOL, 'baz', 10, 13, 'baz'),
            (Token.OPEN_BRACE, '{', 14, 15, '{'),
            (Token.KEYWORD, 'key', 15, 19, ':key'),
            (Token.STRING, 'value', 20, 27, '"value"'),
            (Token.CLOSE_BRACE, '}', 27, 28, '}'),
            (Token.STRING, 'text', 29, 35, '"text"'),
            (Token.CLOSE_BRACKET, ']', 35, 36, ']'),
            (Token.NUMBER, '1', 37, 38, '1'),
            (Token.CLOSE_PAREN, ')', 38, 39, ')'),
            (Token.NEWLINE, '\n', 39, 39, ''),
            (Token.EOF, '', 39, 39, ''),
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
            (Token.SYMBOL, 's1', 0, 2, 's1'),
            (Token.NEWLINE, '\n', 2, 3, '\n'),
            (Token.INDENT, '', 3, 5, '  '),
            (Token.SYMBOL, 's11', 5, 8, 's11'),
            (Token.NEWLINE, '\n', 8, 9, '\n'),
            (Token.INDENT, '', 11, 13, '  '),
            (Token.SYMBOL, 's111', 13, 17, 's111'),
            (Token.NEWLINE, '\n', 17, 18, '\n'),
            (Token.DEDENT, '', 18, 20, '  '),
            (Token.SYMBOL, 's12', 20, 23, 's12'),
            (Token.NEWLINE, '\n', 23, 24, '\n'),
            (Token.SYMBOL, 's13', 26, 29, 's13'),
            (Token.NEWLINE, '\n', 29, 30, '\n'),
            (Token.INDENT, '', 32, 34, '  '),
            (Token.SYMBOL, 's112', 34, 38, 's112'),
            (Token.NEWLINE, '\n', 38, 38, ''),
            (Token.DEDENT, '', 38, 38, ''),
            (Token.DEDENT, '', 38, 38, ''),
            (Token.EOF, '', 38, 38, ''),
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
            (Token.SYMBOL, 'foo', 35, 38, 'foo'),
            (Token.NEWLINE, '\n', 38, 39, '\n'),
            (Token.INDENT, '', 39, 41, '  '),
            (Token.SYMBOL, 'bar', 41, 44, 'bar'),
            (Token.NEWLINE, '\n', 54, 54, ''),
            (Token.DEDENT, '', 54, 54, ''),
            (Token.EOF, '', 54, 54, ''),
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
