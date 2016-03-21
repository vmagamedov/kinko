import types

from kinko.types import StringType
from kinko.lookup import Lookup
from kinko.loaders import DictLoader

from .base import TestCase


A_SRC = """\
def foo
  b/bar
    :arg value
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
        types_ = {
            'value': StringType,
        }
        self.lookup = Lookup(types_, loader)

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

    def testRender(self):
        fn = self.lookup.get('a/foo')
        content = fn.render({'value': 'test'})
        self.assertEqual(content, '<div>test</div>')

    def testEscape(self):
        fn = self.lookup.get('a/foo')
        content = fn.render({
            'value': '<script>alert("xss");</script>',
        })
        self.assertEqual(content, ('<div>&lt;script&gt;alert(&#34;xss&#34;);'
                                   '&lt;/script&gt;</div>'))
