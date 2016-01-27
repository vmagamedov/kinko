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
        self.lookup = Lookup(loader)

    def testDependencies(self):
        self.assertEqual(
            self.lookup.get('a').dependencies,
            {'b'},
        )
        self.assertEqual(
            self.lookup.get('b').dependencies,
            set([]),
        )

    def testLoadDependencies(self):
        self.assertFalse(self.lookup.namespaces)
        ns = self.lookup.get('a')
        self.assertEqual(set(self.lookup.namespaces.keys()), {'a', 'b'})
        self.assertIsInstance(ns.module['a/foo'], types.FunctionType)
