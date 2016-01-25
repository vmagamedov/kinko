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

    def testDependencies(self):
        loader = DictLoader({
            'a': A_SRC,
            'b': B_SRC,
        })
        lookup = Lookup(loader)
        self.assertEqual(
            lookup.get('a').dependencies,
            {'b'},
        )
        self.assertEqual(
            lookup.get('b').dependencies,
            set([]),
        )
