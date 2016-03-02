import types

from kinko.lookup import Lookup
from kinko.loaders import DictLoader

from .base import TestCase


A_SRC = """\
def foo
  b/bar
    :arg "Value"
"""

B_SRC = """\
def bar
  div #arg
"""


class TestLoadCode(TestCase):

    def setUp(self):
        loader = DictLoader({
            'a': A_SRC,
            'b': B_SRC,
        })
        self.lookup = Lookup({}, loader)

    def testDependencies(self):
        self.assertEqual(
            self.lookup._get_namespace('a').dependencies,
            {'b'},
        )
        self.assertEqual(
            self.lookup._get_namespace('b').dependencies,
            set([]),
        )

    def testLoadDependencies(self):
        self.assertFalse(self.lookup._namespaces)
        ns = self.lookup._get_namespace('a')
        self.assertEqual(set(self.lookup._namespaces.keys()), {'a', 'b'})
        self.assertIsInstance(ns.module['foo'], types.FunctionType)
