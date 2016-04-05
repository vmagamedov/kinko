from kinko.nodes import Symbol, Tuple, String, Number, Keyword, Dict, List
from kinko.nodes import Placeholder, NodeVisitor
from kinko.errors import Errors
from kinko.parser import parser, parse as _parse, ParseError, DICT_ERROR
from kinko.parser import IMPLICIT_TUPLE_ERROR, EXPLICIT_TUPLE_ERROR

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


def parse_raw(src):
    node = parser().parse(list(tokenize(src)))
    LocationChecker().visit(node)
    return node


def check_parse(src, node):
    left = parse(src)
    with NODE_EQ_PATCHER:
        assert left == node


def check_location(src, node, start, end, fragment):
    assert node.location
    assert node.location.start.offset == start
    assert node.location.end.offset == end
    assert src[start:end] == fragment


def check_error(src, msg, start, end, fragment):
    errors = Errors()
    try:
        _parse(list(tokenize(src)), errors)
    except ParseError:
        error, = errors.list
        assert error.message.startswith(msg)
        assert (error.location.start.offset, error.location.end.offset) == \
               (start, end)
        assert src[start:end] == fragment
    else:
        raise AssertionError('Error not raised')


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


def test_symbol_location():
    src = 'a b.c\n  d e.f'
    a, bc, _d = parse_raw(src).values[0].values
    d, ef = _d.values
    check_location(src, a, 0, 1, 'a')
    check_location(src, bc, 2, 5, 'b.c')
    check_location(src, d, 8, 9, 'd')
    check_location(src, ef, 10, 13, 'e.f')


def test_string_location():
    src = 'a "b"\n  c "d"'
    a, b, _c = parse_raw(src).values[0].values
    c, d = _c.values
    check_location(src, b, 2, 5, '"b"')
    check_location(src, d, 10, 13, '"d"')


def test_number_location():
    src = 'a 123\n  c 4.56'
    a, n123, _c = parse_raw(src).values[0].values
    c, n456 = _c.values
    check_location(src, n123, 2, 5, '123')
    check_location(src, n456, 10, 14, '4.56')


def test_keyword_location():
    src = 'a :b 1\n  c :d 2'
    a, b, _, _c = parse_raw(src).values[0].values
    c, d, _ = _c.values
    check_location(src, b, 2, 4, ':b')
    check_location(src, d, 11, 13, ':d')


def test_placeholder_location():
    src = 'a #b\n  c #d.e'
    a, b, _c = parse_raw(src).values[0].values
    c, de = _c.values
    check_location(src, b, 2, 4, '#b')
    check_location(src, de, 9, 13, '#d.e')


def test_implicit_tuple_location():
    src = 'a b\n  c\n    :d\n      e'
    fn_a = parse_raw(src).values[0]
    _, _, fn_c = fn_a.values
    _, _, fn_e = fn_c.values
    check_location(src, fn_a, 0, 22, 'a b\n  c\n    :d\n      e')
    check_location(src, fn_c, 6, 22, 'c\n    :d\n      e')
    check_location(src, fn_e, 21, 22, 'e')


def test_explicit_tuple_location():
    src = 'a (b c)'
    fn_a = parse_raw(src).values[0]
    _, fn_b = fn_a.values
    check_location(src, fn_a, 0, 7, 'a (b c)')
    check_location(src, fn_b, 2, 7, '(b c)')


def test_list_location():
    src = 'a [b c]'
    fn_a = parse_raw(src).values[0]
    _, l = fn_a.values
    check_location(src, fn_a, 0, 7, 'a [b c]')
    check_location(src, l, 2, 7, '[b c]')


def test_dict_location():
    src = 'a {:b c}'
    fn_a = parse_raw(src).values[0]
    _, d = fn_a.values
    check_location(src, fn_a, 0, 8, 'a {:b c}')
    check_location(src, d, 2, 8, '{:b c}')


def test_join_location():
    src = 'a b\n  c 1\n  d 2'
    fn_a = parse_raw(src).values[0]
    _, _, j_fn = fn_a.values
    j, l = j_fn.values
    c_fn, d_fn = l.values
    check_location(src, j_fn, 6, 15, 'c 1\n  d 2')
    check_location(src, j, 6, 6, '')
    check_location(src, l, 6, 15, 'c 1\n  d 2')
    check_location(src, c_fn, 6, 9, 'c 1')
    check_location(src, d_fn, 12, 15, 'd 2')


def test_implicit_tuple_error():
    check_error('foo\n1\nbar',
                IMPLICIT_TUPLE_ERROR, 4, 5, '1')


def test_explicit_tuple_error():
    check_error('foo (1 2 3)',
                EXPLICIT_TUPLE_ERROR, 5, 6, '1')


def test_dict_literal_error():
    check_error('foo {1 2}', DICT_ERROR, 5, 6, '1')
