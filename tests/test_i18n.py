# coding: utf-8
from __future__ import unicode_literals

from textwrap import dedent

from kinko.i18n import Extractor, Translator
from kinko.nodes import Tuple, Symbol, String, List
from kinko.compat import PY3
from kinko.parser import parser
from kinko.tokenizer import tokenize

from .base import TestCase, NODE_EQ_PATCHER


class RawParseMixin(object):

    def parse(self, src):
        src = dedent(src).strip() + '\n'
        return parser().parse(list(tokenize(src)))


class TestExtractor(RawParseMixin, TestCase):

    def testString(self):
        node = self.parse(
            """
            div "Some text"
            """
        )
        messages = Extractor.extract(node)
        self.assertEqual(messages, ["Some text"])

    def testWithInterpolation(self):
        node = self.parse(
            """
            div "Some {var} text"
            """
        )
        messages = Extractor.extract(node)
        self.assertEqual(messages, ["Some {var} text"])


class Translations(object):
    messages = {
        'Some {var} text': 'Какой-то {var} текст',
    }
    if PY3:
        def gettext(self, message):
            return self.messages.get(message, message)
    else:
        def ugettext(self, message):
            return self.messages.get(message, message)


class TestTranslator(RawParseMixin, TestCase):
    ctx = [NODE_EQ_PATCHER]

    def setUp(self):
        self.translations = Translations()

    def test(self):
        node = self.parse(
            """
            div "Some {var} text"
            """
        )
        self.assertEqual(
            Translator(self.translations).visit(node),
            List([Tuple([Symbol('div'), String('Какой-то {var} текст')])]),
        )
