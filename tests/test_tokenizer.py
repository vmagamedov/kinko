from textwrap import dedent
from unittest import TestCase

from kinko.tokenizer import Token, tokenize


class TokenizeMixin(object):

    def tokenize(self, src):
        src = dedent(src).strip() + '\n'
        return tokenize(src)


class TestTokenizer(TokenizeMixin, TestCase):
    maxDiff = 1000

    def assertTokens(self, string, tokens):
        left = [(kind, value) for (kind, value, loc) in self.tokenize(string)]
        self.assertEqual(left, tokens)

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
                (Token.SYMBOL, 'Foo'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
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
                (Token.STRING, '123'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
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
                (Token.NUMBER, '9...'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
            ],
        )

    def testKeyword(self):
        self.assertTokens(
            ':foo :foo-bar :foo_bar',
            [
                (Token.KEYWORD, 'foo'),
                (Token.KEYWORD, 'foo-bar'),
                (Token.KEYWORD, 'foo_bar'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
            ],
        )

    def testPlaceholder(self):
        self.assertTokens(
            '#foo #foo-bar #foo_bar #foo.bar',
            [
                (Token.PLACEHOLDER, 'foo'),
                (Token.PLACEHOLDER, 'foo-bar'),
                (Token.PLACEHOLDER, 'foo_bar'),
                (Token.PLACEHOLDER, 'foo.bar'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
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
                (Token.CLOSE_PAREN, ')'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
            ],
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
                (Token.SYMBOL, 's1'), (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 's11'), (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 's111'), (Token.NEWLINE, '\n'),
                (Token.DEDENT, ''),
                (Token.SYMBOL, 's12'), (Token.NEWLINE, '\n'),
                (Token.SYMBOL, 's13'), (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 's112'), (Token.NEWLINE, '\n'),
                (Token.DEDENT, ''),
                (Token.DEDENT, ''),
                (Token.EOF, ''),
            ]
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
                (Token.SYMBOL, 'foo'),
                (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 'bar'),
                (Token.NEWLINE, '\n'),
                (Token.DEDENT, ''),
                (Token.EOF, ''),
            ],
        )
