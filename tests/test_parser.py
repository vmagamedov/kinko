from unittest import TestCase

from funcparserlib.parser import NoParseError

from kinko import nodes as N
from kinko.parser import parser
from kinko.tokenizer import tokenize


class TestParser(TestCase):

    def parse(self, text):
        tokens = list(tokenize(text))
        try:
            return parser().parse(tokens)
        except NoParseError as e:
            print(e.msg, tokens[e.state.pos], tokens[e.state.max])
            print(tokens)
            raise AssertionError("Parse failed: " + e.msg)

    def testSimple(self):
        self.assertEqual(self.parse('div "text"'), [
            N.Tuple(N.Symbol('div'), [N.String("text")])
        ])

    def testNested(self):
        self.assertEqual(self.parse("""div "text"
            div 12
        """), [
            N.Tuple(N.Symbol('div'), [
                N.String("text"),
                N.Tuple(N.Symbol("div"), [N.Number(12)]),
                ])
        ])

    def testKeyword(self):
        self.assertEqual(self.parse('div :class "red" "text"'), [
            N.Tuple(N.Symbol('div'), [
                N.KeywordPair(N.Keyword("class"), N.String("red")),
                N.String("text"),
            ])
        ])
