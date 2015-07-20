from unittest import TestCase

from funcparserlib.parser import NoParseError

from kinko import nodes as N
from kinko.parser import parser
from kinko.tokenizer import tokenize
from kinko.compiler import compile_template


class TestParser(TestCase):

    def parse(self, text):
        tokens = list(tokenize(text))
        try:
            body = parser().parse(tokens)
        except NoParseError as e:
            print(e.msg, tokens[e.state.pos], tokens[e.state.max])
            print(tokens)
            raise AssertionError("Parse failed: " + e.msg)
        return str(compile_template(body))

    def testSimple(self):
        self.assertEqual(self.parse('div "text"'), "div('text')")

    def testNested(self):
        self.assertEqual(self.parse('div "text"\n  p (b "hello")'),
                                    "div('text', p(b('hello')))")

    def testAttr(self):
        self.assertEqual(self.parse('render product.name'),
                                    'render(product.name)')
