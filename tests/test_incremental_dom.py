# encoding: utf-8
import difflib
from textwrap import dedent

from kinko.types import StringType, ListType, Func, VarNamedArgs, Record
from kinko.types import IntType, NamedArg, Markup
from kinko.checker import check, Environ
from kinko.compile.incremental_dom import compile_module, dumps

from .base import TestCase
from .test_parser import ParseMixin


class TestIncrementalDOM(ParseMixin, TestCase):

    def assertCompiles(self, src, code, env=None):
        node = self.parse(src)
        node = check(node, Environ(env or {}))
        mod = compile_module(node)
        first = dumps(mod).strip()
        second = dedent(code).strip()
        if first != second:
            msg = ('Compiled code is not equal:\n\n{}'
                   .format('\n'.join(difflib.ndiff(first.splitlines(),
                                                   second.splitlines()))))
            raise self.failureException(msg)

    def testTag(self):
        self.assertCompiles(
            """
            div :foo "bar" "baz"
            """,
            """
            elementOpen("div", "", [], ["foo","bar"]);
            text("baz");
            elementClose("div");
            """,
        )

    def testSymbol(self):
        self.assertCompiles(
            """
            div :foo "bar" baz
            """,
            """
            elementOpen("div", "", [], ["foo","bar"]);
            text(ctx["baz"]);
            elementClose("div");
            """,
            {'baz': StringType},
        )

    def testJoin(self):
        self.assertCompiles(
            """
            div
              div "one"
              div "two"
            """,
            """
            elementOpen("div", "", [], []);
            elementOpen("div", "", [], []);
            text("one");
            elementClose("div");
            elementOpen("div", "", [], []);
            text("two");
            elementClose("div");
            elementClose("div");
            """,
        )

    def testEach(self):
        self.assertCompiles(
            """
            div
              each i items
                div i
            """,
            """
            elementOpen("div", "", [], []);
            for (var _i = 0; _i < ctx["items"].length; _i++) {
              var i = ctx["items"][_i];
              elementOpen("div", "", [], []);
              text(i);
              elementClose("div");
            }
            elementClose("div");
            """,
            {'items': ListType[StringType]},
        )

    def testBuiltinFuncCall(self):
        self.assertCompiles(
            """
            a :href (url-for "foo" :bar "baz")
            """,
            """
            elementOpen("a", "", [], ["href",builtins.url-for("foo", {
              "bar": "baz"
            })]);
            elementClose("a");
            """,
            {'url-for': Func[[StringType, VarNamedArgs[StringType]],
                             StringType]},
        )

    def testFuncDef(self):
        self.assertCompiles(
            """
            def func
              div :class #foo
                #bar
                each i items
                  div
                    #baz
            """,
            """
            function func(foo, bar, baz) {
              elementOpen("div", "", [], ["class",foo]);
              bar();
              for (var _i = 0; _i < ctx["items"].length; _i++) {
                var i = ctx["items"][_i];
                elementOpen("div", "", [], []);
                baz();
                elementClose("div");
              }
              elementClose("div");
            }
            """,
            {'items': ListType[Record[{}]]},
        )

    def testFuncCall(self):
        self.assertCompiles(
            """
            div
              foo/bar 1 2
                :param1
                  div
                    ./baz 3 4 :param2 "Test"
            """,
            """
            elementOpen("div", "", [], []);
            foo.bar(1, 2, function() {
              elementOpen("div", "", [], []);
              baz(3, 4, "Test");
              elementClose("div");
            });
            elementClose("div");
            """,
            {'foo/bar': Func[[IntType, IntType, NamedArg['param1', Markup]],
                             Markup],
             './baz': Func[[IntType, IntType, NamedArg['param2', StringType]],
                           Markup]},
        )

    def testIf(self):
        self.assertCompiles(
            """
            if 1
              div "Trueish"
            """,
            """
            if (1) {
              elementOpen("div", "", [], []);
              text("Trueish");
              elementClose("div");
            }
            """,
        )
        self.assertCompiles(
            """
            div
              if (if 1 "true" "false")
                span "Trueish"
            """,
            """
            elementOpen("div", "", [], []);
            if (1 ? "true" : "false") {
              elementOpen("span", "", [], []);
              text("Trueish");
              elementClose("span");
            }
            elementClose("div");
            """,
        )
        self.assertCompiles(
            """
            div
              if (if 1 "true")
                span "Trueish"
            """,
            """
            elementOpen("div", "", [], []);
            if (1 ? "true" : null) {
              elementOpen("span", "", [], []);
              text("Trueish");
              elementClose("span");
            }
            elementClose("div");
            """,
        )

    def testGet(self):
        self.assertCompiles(
            """
            div :class foo.bar.baz
            """,
            """
            elementOpen("div", "", [], ["class",ctx["foo"]["bar"]["baz"]]);
            elementClose("div");
            """,
            {'foo': Record[{'bar': Record[{'baz': StringType}]}]},
        )
