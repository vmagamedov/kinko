from __future__ import unicode_literals

from kinko.read.simple import loads

from .base import TestCase, ResultMixin


class TestReadSimple(ResultMixin, TestCase):

    def test(self):
        self.assertResult(
            loads("""
            {
              "f1" 1
              "a" {"f2" 2}
              "b" {
                1 {"f3" "bar1"}
                2 {"f3" "bar2"}
                3 {"f3" "bar3"}
              }
              "l1" #graph/ref ["b" 1]
              "l2" [#graph/ref ["b" 2]
                    #graph/ref ["b" 3]]
            }
            """),
            {'f1': 1,
             'a': {'f2': 2},
             'l1': {'f3': 'bar1'},
             'l2': [
                 {'f3': 'bar2'},
                 {'f3': 'bar3'},
             ]},
        )
