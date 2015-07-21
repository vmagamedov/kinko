from unittest import TestCase

from kinko.tokenizer import Token, tokenize


class TestTokenizer(TestCase):
    maxDiff = 1000

    def assertTokens(self, string, tokens):
        left = [(kind, value) for (kind, value, loc) in tokenize(string)]
        self.assertEqual(left, tokens)

    def testSimple(self):
        self.assertTokens('div "text"', [
            (Token.SYMBOL, 'div'),
            (Token.STRING, 'text'),
            (Token.NEWLINE, '\n'),
            (Token.EOF, ''),
        ])

    def testOneLetter(self):
        self.assertTokens('b "text"', [
            (Token.SYMBOL, 'b'),
            (Token.STRING, 'text'),
            (Token.NEWLINE, '\n'),
            (Token.EOF, ''),
        ])

    def testTokenEof(self):
        self.assertTokens('token', [
            (Token.SYMBOL, 'token'),
            (Token.NEWLINE, '\n'),
            (Token.EOF, ''),
        ])

    def testIndent(self):
        self.assertTokens(
            'def hello\n'
            '  div :class "world"\n'
            '    "text"\n'
            '    div\n'
            '      div\n'
            '        "content"\n'
            '    span "value"\n'
            '  pre\n',
            [
                (Token.SYMBOL, 'def'),
                (Token.SYMBOL, 'hello'),
                (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 'div'),
                (Token.KEYWORD, 'class'),
                (Token.STRING, 'world'),
                (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.STRING, 'text'),
                (Token.NEWLINE, '\n'),
                (Token.SYMBOL, 'div'),
                (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 'div'),
                (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.STRING, 'content'),
                (Token.NEWLINE, '\n'),
                (Token.DEDENT, ''),
                (Token.DEDENT, ''),
                (Token.SYMBOL, 'span'),
                (Token.STRING, 'value'),
                (Token.NEWLINE, '\n'),
                (Token.DEDENT, ''),
                (Token.SYMBOL, 'pre'),
                (Token.NEWLINE, '\n'),
                (Token.DEDENT, ''),
                (Token.EOF, ''),
            ],
        )

    def testComments(self):
        self.assertTokens(
            '; comment\n'
            'def hello\n'
            '  div :class "world"\n'
            '    ; whatever\n'
            '    span "value" ; whatever\n',
            [
                (Token.SYMBOL, 'def'),
                (Token.SYMBOL, 'hello'),
                (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 'div'),
                (Token.KEYWORD, 'class'),
                (Token.STRING, 'world'),
                (Token.NEWLINE, '\n'),
                (Token.INDENT, ''),
                (Token.SYMBOL, 'span'),
                (Token.STRING, 'value'),
                (Token.NEWLINE, '\n'),
                (Token.DEDENT, ''),
                (Token.DEDENT, ''),
                (Token.EOF, ''),
            ],
        )

    def testKeyword(self):
        self.assertTokens(
            'div :class "red"',
            [
                (Token.SYMBOL, 'div'),
                (Token.KEYWORD, 'class'),
                (Token.STRING, 'red'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
            ],
        )

    def testBrackets(self):
        self.assertTokens(
            '(div\n'
            '  :class "red")',
            [
                (Token.OPEN_PAREN, '('),
                (Token.SYMBOL, 'div'),
                (Token.KEYWORD, 'class'),
                (Token.STRING, 'red'),
                (Token.CLOSE_PAREN, ')'),
                (Token.NEWLINE, '\n'),
                (Token.EOF, ''),
            ],
        )
