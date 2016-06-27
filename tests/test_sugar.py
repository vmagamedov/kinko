from kinko.nodes import Tuple, Symbol, List, String
from kinko.sugar import InterpolateString, TranslateDots, TransformError
from kinko.errors import Errors

from .base import NODE_EQ_PATCHER
from .test_parser import parse, parse_raw


def interpolate(node):
    return InterpolateString().visit(node)


def translate(node, errors):
    return TranslateDots(errors).visit(node)


def check_eq(first, second):
    with NODE_EQ_PATCHER:
        assert first == second


def check_location(src, node, fragment):
    a, b = node.location.start.offset, node.location.end.offset
    assert src[a:b] == fragment


def check_error(src, msg, fragment):
    errors = Errors()
    try:
        translate(parse_raw(src), errors),
    except TransformError:
        error, = errors.list
        assert error.message.startswith(msg)
        start = error.location.start.offset
        end = error.location.end.offset
        assert src[start:end] == fragment
    else:
        raise AssertionError('Error not raised')


def test_interpolate():
    src = 'foo "before {a} {b.c} after"'
    node = interpolate(parse_raw(src))
    check_eq(
        node,
        List([Tuple([
            Symbol('foo'),
            Tuple([Symbol('join'), List([
                String('before '),
                Symbol('a'),
                String(' '),
                Symbol('b.c'),
                String(' after'),
            ])]),
        ])]),
    )
    items = node.values[0].values[1].values[1].values
    check_location(src, items[0], '"before ')
    check_location(src, items[1], 'a')
    check_location(src, items[2], ' ')
    check_location(src, items[3], 'b.c')
    check_location(src, items[4], ' after"')


def test_interpolate_first():
    src = 'foo "{a} after"'
    node = interpolate(parse_raw(src))
    check_eq(
        node,
        List([Tuple([
            Symbol('foo'),
            Tuple([Symbol('join'), List([
                Symbol('a'),
                String(' after'),
            ])]),
        ])]),
    )
    items = node.values[0].values[1].values[1].values
    check_location(src, items[0], 'a')
    check_location(src, items[1], ' after"')


def test_interpolate_last():
    src = 'foo "before {a}"'
    node = interpolate(parse_raw(src))
    check_eq(
        node,
        List([Tuple([
            Symbol('foo'),
            Tuple([Symbol('join'), List([
                String('before '),
                Symbol('a'),
            ])]),
        ])]),
    )
    items = node.values[0].values[1].values[1].values
    check_location(src, items[0], '"before ')
    check_location(src, items[1], 'a')


def test_interpolate_var_only():
    src = 'foo "{a}"'
    node = interpolate(parse_raw(src))
    check_eq(
        node,
        List([Tuple([
            Symbol('foo'),
            Symbol('a'),
        ])]),
    )
    check_location(src, node.values[0].values[1], 'a')


def test_interpolate_string_only():
    src = 'foo "text"'
    node = interpolate(parse_raw(src))
    check_eq(
        node,
        List([Tuple([
            Symbol('foo'),
            String('text'),
        ])]),
    )
    check_location(src, node.values[0].values[1], '"text"')


def test_interpolate_empty_string():
    src = 'foo ""'
    node = interpolate(parse_raw(src))
    check_eq(
        node,
        List([Tuple([
            Symbol('foo'),
            String(''),
        ])]),
    )
    check_location(src, node.values[0].values[1], '""')


def test_interpolate_invalid():
    check_eq(
        interpolate(parse_raw('foo "before {.a} {b.} {a..b} {.} '
                              '{..} after"')),
        List([Tuple([
            Symbol('foo'),
            String('before {.a} {b.} {a..b} {.} {..} after'),
        ])]),
    )
    check_eq(
        interpolate(parse_raw('foo "before {.a} {b.} {c} {a..b} '
                              '{.} {..} after"')),
        List([Tuple([
            Symbol('foo'),
            Tuple([Symbol('join'), List([
                String('before {.a} {b.} '),
                Symbol('c'),
                String(' {a..b} {.} {..} after'),
            ])]),
        ])]),
    )


def test_parser_interpolate():
    node = parse("""
    foo
      "bar {value} baz"
    """)
    check_eq(
        node,
        List([
            Tuple([
                Symbol('foo'),
                Tuple([Symbol('join'), List([
                    String('bar '),
                    Symbol('value'),
                    String(' baz'),
                ])]),
            ]),
        ]),
    )


def test_translate_dots_invalid():
    check_error('foo\n  bar.baz', 'Symbol in this position',
                'bar.baz')
