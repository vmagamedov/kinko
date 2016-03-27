from kinko.nodes import Symbol, Tuple, String, Number, Keyword, Dict, List
from kinko.nodes import Placeholder, NodeVisitor
from kinko.parser import parse as _parse

from .base import NODE_EQ_PATCHER
from .test_tokenizer import tokenize


class LocationChecker(NodeVisitor):

    def visit(self, node):
        assert node.location
        super(LocationChecker, self).visit(node)


def parse(src):
    node = _parse(list(tokenize(src)))
    LocationChecker().visit(node)
    return node


def check_parse(src, node):
    left = parse(src)
    with NODE_EQ_PATCHER:
        assert left == node


def test_symbol():
    assert Symbol('foo').ns is None
    assert Symbol('foo').rel == 'foo'
    assert Symbol('foo').name == 'foo'
    assert Symbol('./foo').ns == '.'
    assert Symbol('./foo').rel == 'foo'
    assert Symbol('./foo').name == './foo'
    assert Symbol('foo/bar').ns == 'foo'
    assert Symbol('foo/bar').rel == 'bar'
    assert Symbol('foo/bar').name == 'foo/bar'
    check_parse(
        'print foo foo.bar foo.bar.baz foo/bar.baz ./foo.bar',
        List([
            Tuple([Symbol('print'),
                   Symbol('foo'),
                   Tuple([Symbol('get'),
                          Symbol('foo'), Symbol('bar')]),
                   Tuple([Symbol('get'),
                          Tuple([Symbol('get'),
                                 Symbol('foo'), Symbol('bar')]),
                          Symbol('baz')]),
                   Tuple([Symbol('get'),
                          Symbol('foo/bar'), Symbol('baz')]),
                   Tuple([Symbol('get'),
                          Symbol('./foo'), Symbol('bar')])]),
        ]),
    )


def test_placeholder():
    check_parse(
        'print #foo #foo.bar #foo.bar.baz',
        List([
            Tuple([Symbol('print'),
                   Placeholder('foo'),
                   Tuple([Symbol('get'),
                          Placeholder('foo'), Symbol('bar')]),
                   Tuple([Symbol('get'),
                          Tuple([Symbol('get'),
                                 Placeholder('foo'), Symbol('bar')]),
                          Symbol('baz')])]),
        ]),
    )


def test_implicit_tuple():
    check_parse(
        'foo :bar 5 "baz"',
        List([
            Tuple([Symbol('foo'),
                   Keyword('bar'), Number(5), String('baz')]),
        ]),
    )


def test_explicit_tuple():
    check_parse(
        'foo (bar 5) "baz"',
        List([
            Tuple([Symbol('foo'), Tuple([Symbol('bar'), Number(5)]),
                   String('baz')]),
        ]),
    )


def test_list():
    check_parse(
        'foo [:k1 v1 1 (foo 2)]',
        List([
            Tuple([Symbol('foo'),
                   List([Keyword('k1'),
                         Symbol('v1'),
                         Number(1),
                         Tuple([Symbol('foo'), Number(2)])])]),
        ]),
    )


def test_dict():
    check_parse(
        'foo {:k1 v1 :k2 (v2 3)}',
        List([
            Tuple([Symbol('foo'),
                   Dict([Keyword('k1'), Symbol('v1'),
                         Keyword('k2'), Tuple([Symbol('v2'),
                                               Number(3)])])]),
        ]),
    )


def test_indent():
    check_parse(
        """
        foo
          "bar"
        """,
        List([
            Tuple([Symbol('foo'), String('bar')]),
        ]),
    )
    check_parse(
        """
        foo
          "bar"
          5
          "baz"
        """,
        List([
            Tuple([Symbol('foo'),
                   Tuple([Symbol('join'),
                          List([String('bar'), Number(5),
                                String('baz')])])]),
        ]),
    )


def test_nested_indent():
    check_parse(
        """
        foo
          bar
            1
          baz
            2
        """,
        List([
            Tuple([Symbol('foo'),
                   Tuple([Symbol('join'),
                          List([Tuple([Symbol('bar'), Number(1)]),
                                Tuple([Symbol('baz'), Number(2)])])])]),
        ]),
    )


def test_indented_keywords():
    check_parse(
        """
        foo :k1 v1
          :k2 v2
          :k3
            v3
        """,
        List([
            Tuple([Symbol('foo'),
                   Keyword('k1'), Symbol('v1'),
                   Keyword('k2'), Symbol('v2'),
                   Keyword('k3'), Tuple([Symbol('v3')])]),
        ]),
    )


def test_mixed_indented_arguments():
    check_parse(
        """
        foo :k1 v1
          :k2 v2
          :k3
            v3
          v4
          v5
        """,
        List([
            Tuple([Symbol('foo'),
                   Keyword('k1'), Symbol('v1'),
                   Keyword('k2'), Symbol('v2'),
                   Keyword('k3'), Tuple([Symbol('v3')]),
                   Tuple([Symbol('join'),
                          List([Tuple([Symbol('v4')]),
                                Tuple([Symbol('v5')])])])]),
        ]),
    )
