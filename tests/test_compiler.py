from unittest import TestCase

from funcparserlib.parser import NoParseError

from kinko import nodes as N
from kinko.parser import parser
from kinko.tokenizer import tokenize
from kinko.translate import translate_template
from kinko.compiler import compile_to_string


class TestParser(TestCase):

    def parse(self, text):
        tokens = list(tokenize(text))
        try:
            body = parser().parse(tokens)
        except NoParseError as e:
            print(e.msg, tokens[e.state.pos], tokens[e.state.max])
            print(tokens)
            raise AssertionError("Parse failed: " + e.msg)
        ast = translate_template(body)
        return str(compile_to_string(ast))

    def testSimple(self):
        self.assertEqual(self.parse('def main\n div "text"'), "div('text')")

    def testNested(self):
        self.assertEqual(self.parse('def main\n div "text"\n  p (b "hello")'),
                                    "div('text', p(b('hello')))")

    def testAttr(self):
        self.assertEqual(self.parse('def main\n render product.name'),
                                    'render(product.name)')
