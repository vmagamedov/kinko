from textwrap import dedent
from unittest import TestCase

from kinko.errors import Errors
from kinko.tokenizer import Token, tokenize, TokenizerError


NL = (Token.NEWLINE, '\n')

EOF = (Token.EOF, '')


class TokenizeMixin(object):

    def tokenize(self, src, errors=None):
        src = dedent(src).strip() + '\n'
        return tokenize(src, errors)


class TestTokenizer(TokenizeMixin, TestCase):
    maxDiff = 1000

    def assertTokens(self, string, tokens):
        left = [(kind, value) for (kind, value, loc) in self.tokenize(string)]
        self.assertEqual(left, tokens)

    def assertErrors(self, string, messages):
        errors = Errors()
        try:
            list(self.tokenize(string, errors))
        except TokenizerError:
            errors_map = {e.message for e in errors.list}
            self.assertEqual(errors_map, set(messages))
        else:
            self.fail('No errors')

    def testSymbol(self):
        self.assertTokens(
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

    def testString(self):
        self.assertTokens(
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

    def testNumber(self):
        self.assertTokens(
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

    def testKeyword(self):
        self.assertTokens(
            ':foo :foo-bar :foo_bar',
            [
                (Token.KEYWORD, 'foo'),
                (Token.KEYWORD, 'foo-bar'),
                (Token.KEYWORD, 'foo_bar'), NL,
                EOF,
            ],
        )

    def testPlaceholder(self):
        self.assertTokens(
            '#foo #foo-bar #foo_bar #foo.bar',
            [
                (Token.PLACEHOLDER, 'foo'),
                (Token.PLACEHOLDER, 'foo-bar'),
                (Token.PLACEHOLDER, 'foo_bar'),
                (Token.PLACEHOLDER, 'foo.bar'), NL,
                EOF,
            ],
        )

    def testBrackets(self):
        self.assertTokens(
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

    def testIncompleteParentheses(self):
        for bracket in '[({':
            self.assertErrors(
                """
                foo {}bar
                """.format(bracket),
                ['Not closed parenthesis'],
            )

    def testInvalidParentheses(self):
        params = [(a, b, c) for a, b in zip('[({', '])}')
                  for c in '])}' if b != c]
        for open_bracket, closing_bracket, invalid_bracket in params:
            self.assertErrors(
                """
                foo {}bar{}
                """.format(open_bracket, invalid_bracket),
                ["Unmatching parenthesis, expected '{}' got '{}'"
                 .format(closing_bracket, invalid_bracket)],
            )

    def testUnknownParentheses(self):
        for bracket in '])}':
            self.assertErrors(
                """
                foo bar{}
                """.format(bracket),
                ["No parenthesis matching '{}'".format(bracket)],
            )

    def testIndent(self):
        self.assertTokens(
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

    def testIndentWithTabs(self):
        self.assertErrors(
            """
            a
            \tb
            """,
            ['Please indent by spaces'],
        )

    def testInvalidDedent(self):
        self.assertErrors(
            """
            a
              b
             c
            """,
            ['Indentation level mismatch'],
        )

    def testComments(self):
        self.assertTokens(
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
