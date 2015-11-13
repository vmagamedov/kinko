from kinko.checker import check, Environ
from kinko.refs import NamedArgRef
from .base import TestCase, REF_EQ_PATCHER
from .test_parser import ParseMixin


class TestRefs(ParseMixin, TestCase):
    ctx = [REF_EQ_PATCHER]

    def parse_expr(self, src):
        return self.parse(src).values[0]

    def check(self, src, env=None):
        return check(self.parse_expr(src), Environ(env))

    def testDef(self):
        foo = self.check("""
        def foo
          span #arg
        """)
        arg = foo.values[2].values[1]
        self.assertEqual(arg.__type__.__ref__, NamedArgRef('arg'))
