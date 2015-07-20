from unittest import TestCase

from funcparserlib.parser import NoParseError

from kinko import nodes as N
from kinko.parser import parser
from kinko.tokenizer import tokenize
from kinko.translate import translate_template
from kinko.compiler import compile_to_string


class TestCompiler(TestCase):

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
        self.assertEqual(self.parse('def main\n div "text"'),
            "def main(buf):\n    div(buf, (lambda buf: buf.write('text')))")

    def testText(self):
        self.assertEqual(self.parse('def main\n "text"'),
            "def main(buf):\n    buf.write('text')")

    def testText2(self):
        self.assertEqual(self.parse('def main\n "a"\n "b"'),
            "def main(buf):\n    buf.write('a')\n    buf.write('b')")

    def testTwo(self):
        self.assertEqual(self.parse('def main\n p "1"\n p "2"'),
            "def main(buf):\n"
            "    p(buf, (lambda buf: buf.write('1')))\n"
            "    p(buf, (lambda buf: buf.write('2')))")

    def testNested(self):
        self.assertEqual(self.parse('def main\n div "text"\n  p (b "hello")'),
            "def main(buf):\n"
            "    div(buf, (lambda buf: buf.write('text')),"
                        " (lambda buf: p(buf,"
                        " (lambda buf: b(buf,"
                        " (lambda buf:"
                        " buf.write('hello')))))))")

    def testAttr(self):
        self.assertEqual(self.parse('def main\n render product.name'),
            'def main(buf):\n'
            '    render(buf, (lambda buf: buf.write(product.name)))')
