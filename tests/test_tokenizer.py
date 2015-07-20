from unittest import TestCase
from kinko.tokenizer import tokenize


class TestTokenizer(TestCase):
    maxDiff = 1000

    def assert_tokens(self, string, tokens):
        left = [(kind.value, value) for (kind, value, loc) in tokenize(string)]
        self.assertEqual(left, tokens)

    def testSimple(self):
        self.assert_tokens('div "text"', [
            ("ident", "div"),
            ("string", '"text"'),
            ("newline", '\n'),
            ("eof", ''),
        ])

    def testOneLetter(self):
        self.assert_tokens('b "text"', [
            ("ident", "b"),
            ("string", '"text"'),
            ("newline", '\n'),
            ("eof", ''),
        ])

    def testTokenEof(self):
        self.assert_tokens('token', [
            ("ident", "token"),
            ("newline", '\n'),
            ("eof", ''),
        ])

    indent_comment_tokens = [
        ("ident", 'def'),
        ("ident", 'hello'),
        ("newline", '\n'),
        ("indent", ''),
        ("ident", 'div'),
        ("keyword", 'class'),
        ("string", '"world"'),
        ("newline", '\n'),
        ("indent", ''),
        ("string", '"text"'),
        ("newline", '\n'),
        ("ident", 'div'),
        ("newline", '\n'),
        ("indent", ''),
        ("ident", 'div'),
        ("newline", '\n'),
        ("indent", ''),
        ("string", '"content"'),
        ("newline", '\n'),
        ("dedent", ''),
        ("dedent", ''),
        ("ident", 'span'),
        ("string", '"value"'),
        ("newline", '\n'),
        ("dedent", ''),
        ("ident", 'pre'),
        ("newline", '\n'),
        ("dedent", ''),
        ("eof", ''),
    ]

    def testindent(self):
        self.assert_tokens("""def hello
            div :class "world"
                "text"
                div
                    div
                        "content"
                span "value"
            pre
        """, self.indent_comment_tokens)

    def testcomments(self):
        self.assert_tokens("""def hello
            div :class "world"
                    ; whatever
                "text"
                div
                    div
                        "content"
            ; whatever
                span "value" ; whaverver
            pre
        """, self.indent_comment_tokens)


    def testKeyword(self):
        self.assert_tokens('div :class "red"', [
            ("ident", "div"),
            ("keyword", 'class'),
            ("string", '"red"'),
            ("newline", '\n'),
            ("eof", ''),
        ])

    def testBrackets(self):
        self.assert_tokens('''(div
            :class "red"
        )''', [
            ("open_paren", "("),
            ("ident", "div"),
            ("keyword", 'class'),
            ("string", '"red"'),
            ("close_paren", ")"),
            ("newline", '\n'),
            ("eof", ''),
        ])












