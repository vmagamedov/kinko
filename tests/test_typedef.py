import weakref
from textwrap import dedent

from kinko.types import Record, StringType, IntType, ListType, Func, TypeRef
from kinko.typedef import load_types

from .base import TestCase, TYPE_EQ_PATCHER


class TestTypeDefinition(TestCase):
    ctx = [TYPE_EQ_PATCHER]

    def test(self):
        src = """
        type func
          Fn [String Integer] String

        type Foo
          Record
            :name String
            :type Integer

        type Bar
          Record
            :name String
            :foo-list (List Foo)

        type Baz
          Record
            :name String
            :type Integer
            :bar Bar
        """
        src = dedent(src).strip() + '\n'

        func_type = Func[[StringType, IntType], StringType]

        FooType = Record[{'name': StringType, 'type': IntType}]

        BarType = Record[{'name': StringType,
                          'foo-list': ListType[TypeRef['Foo']]}]
        BarType.__items__['foo-list'].__item_type__.__ref__ = \
            weakref.ref(FooType)

        BazType = Record[{'name': StringType, 'type': IntType,
                          'bar': TypeRef['Bar']}]
        BazType.__items__['bar'].__ref__ = weakref.ref(BarType)

        self.assertEqual(
            load_types(src),
            {
                'func': func_type,
                'Foo': FooType,
                'Bar': BarType,
                'Baz': BazType,
            },
        )
