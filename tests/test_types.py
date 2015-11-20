from kinko.types import issubtype, IntType, BoolType, Record

from .base import TestCase


class TestTypes(TestCase):

    def testIsSubtype(self):
        self.assertTrue(issubtype(IntType, BoolType))
        self.assertTrue(issubtype(Record[{'a': BoolType, 'b': IntType}],
                                  Record[{'a': BoolType, 'b': BoolType}]))
