from kinko.nodes import Number, Keyword
from kinko.utils import split_args

from .base import TestCase, node_eq_patcher


class TestUtils(TestCase):
    ctx = [node_eq_patcher]

    def testSplitArgs(self):
        self.assertEqual(
            split_args([Number(1), Number(2), Keyword('foo'), Number(3)]),
            ([Number(1), Number(2)], {'foo': Number(3)}),
        )
        self.assertEqual(
            split_args([Keyword('foo'), Number(1), Number(2), Number(3)]),
            ([Number(2), Number(3)], {'foo': Number(1)}),
        )
        with self.assertRaises(TypeError):
            split_args([Number(1), Keyword('foo')])
