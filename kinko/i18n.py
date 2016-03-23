from .nodes import NodeVisitor, NodeTransformer
from .compat import PY3


class Extractor(NodeVisitor):

    def __init__(self):
        self._messages = set([])

    @classmethod
    def extract(cls, node):
        self = cls()
        self.visit(node)
        return list(self._messages)

    def visit_string(self, node):
        self._messages.add(node.value)


class Translator(NodeTransformer):

    def __init__(self, translations):
        self.translations = translations
        self._gettext = (self.translations.gettext if PY3
                         else self.translations.ugettext)

    def visit_string(self, node):
        string = node.clone()
        string.value = self._gettext(node.value)
        return string
