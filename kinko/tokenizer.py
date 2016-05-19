try:
    from sys import intern
except ImportError:
    pass

from string import ascii_letters, digits, whitespace
from collections import namedtuple

from .errors import UserError, Errors


MINUS = '-'
SLASH = '/'
UNDSCR = '_'
DOT = '.'

KEYWORD_CHARS = ascii_letters + digits + MINUS + UNDSCR
PLACEHOLDER_CHARS = ascii_letters + digits + MINUS + UNDSCR + DOT
SYMBOL_CHARS = ascii_letters + digits + MINUS + UNDSCR + DOT + SLASH
NUMBER_CHARS = ascii_letters + digits + DOT


_Token = namedtuple('_Token', 'type value location')


class Token(_Token):
    KEYWORD = intern('keyword')
    PLACEHOLDER = intern('placeholder')
    NEWLINE = intern('newline')
    STRING = intern('string')
    SYMBOL = intern('symbol')
    NUMBER = intern('number')
    OPEN_BRACE = intern('open_brace')
    OPEN_PAREN = intern('open_paren')
    OPEN_BRACKET = intern('open_bracket')
    CLOSE_BRACE = intern('close_brace')
    CLOSE_PAREN = intern('close_paren')
    CLOSE_BRACKET = intern('close_bracket')
    INDENT = intern('indent')
    DEDENT = intern('dedent')
    EOF = intern('eof')

    def __repr__(self):
        return '<{} {!r} {}:{}>'.format(self.type, self.value,
                                        self.location.start.line,
                                        self.location.start.column)


BRACKET_TYPES = {
    '{': Token.OPEN_BRACE,
    '(': Token.OPEN_PAREN,
    '[': Token.OPEN_BRACKET,
    '}': Token.CLOSE_BRACE,
    ')': Token.CLOSE_PAREN,
    ']': Token.CLOSE_BRACKET,
}

MATCHING_BRACKET = {
    '{': '}',
    '(': ')',
    '[': ']',
}


class TokenizerError(UserError):
    pass


class _Interrupt(Exception):
    pass


_Position = namedtuple('Position', 'offset line column')


class Position(_Position):

    def __index__(self):
        return self.offset


Location = namedtuple('Location', 'start end')


class Chars(object):
    def __init__(self, string):
        self.string = string
        self.index = 0
        self.line = 1
        self.pos = 1

    def __iter__(self):
        return self

    def __next__(self):
        rpos = self.next_position
        if self.index >= len(self.string):
            raise StopIteration()
        char = self.string[self.index]
        self.index += 1
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.pos = 1
        return rpos, char
    next = __next__  # crappy py2

    def peek_in(self, valid_chars):
        try:
            return self.string[self.index] in valid_chars
        except IndexError:
            return False

    @property
    def next_position(self):
        return Position(self.index, self.line, self.pos)

    def location_from(self, pos):
        return Location(pos, self.next_position)


def read_slice(char_iter, valid_chars, type_, start=None, start_pos=None):
    start = start or char_iter.next_position
    start_pos = start_pos or start
    while char_iter.peek_in(valid_chars):
        next(char_iter)
    end = char_iter.next_position
    return Token(type_, char_iter.string[start:end],
                 Location(start_pos, end))


def read_string(char_iter, start, quote, errors):
    start = start or char_iter.next_position
    for pos, ch in char_iter:
        if ch == '\'':
            try:
                next(char_iter)  # skip next character regardless of value
            except StopIteration:
                break
        elif ch == quote:
            quote_from = start.offset + 1
            quote_to = char_iter.next_position.offset - 1
            return Token(Token.STRING, char_iter.string[quote_from: quote_to],
                         char_iter.location_from(start))
        elif ch == '\n':
            with errors.location(char_iter.location_from(start)):
                raise TokenizerError("Newlines are not allowed in strings")

    with errors.location(char_iter.location_from(start)):
        raise TokenizerError("String does not and at EOF")


def tokenize(string, errors=None):
    errors = Errors() if errors is None else errors
    char_iter = Chars(string)
    brackets = []
    indents = [1]
    for pos, ch in char_iter:
        try:
            while pos.column == 1 and not brackets:
                start = pos
                while ch in whitespace:
                    if ch != ' ':
                        if ch == '\n':
                            break
                        with errors.location(char_iter.location_from(start)):
                            raise TokenizerError("Please indent by spaces")
                    try:
                        pos, ch = next(char_iter)
                    except StopIteration:
                        raise _Interrupt()
                if ch == ';':
                    # ignore comments
                    for _, ch in char_iter:
                        if ch == '\n':
                            break
                    try:
                        pos, ch = next(char_iter)
                    except StopIteration:
                        raise _Interrupt()
                    continue
                elif ch == '\n':
                    # ignore empty lines
                    try:
                        pos, ch = next(char_iter)
                    except StopIteration:
                        raise _Interrupt()
                    continue
                cur_indent = indents[-1]
                new_indent = pos.column
                loc = Location(start, pos)
                if new_indent < cur_indent:
                    try:
                        ident_pos = indents.index(new_indent)
                    except ValueError:
                        with errors.location(loc):
                            raise TokenizerError("Indentation level mismatch")
                    else:
                        for _i in range(ident_pos+1, len(indents)):
                            yield Token(Token.DEDENT, '', loc)
                        del indents[ident_pos+1:]
                elif new_indent > cur_indent:
                    size = new_indent - cur_indent
                    loc = Location(Position(pos.offset - size, pos.line,
                                            pos.column - size), pos)
                    indents.append(new_indent)
                    yield Token(Token.INDENT, '', loc)
                break
        except _Interrupt:
            break
        if ch == ':':
            yield read_slice(char_iter, KEYWORD_CHARS, Token.KEYWORD,
                             start_pos=pos)
        elif ch == ';':
            for pos, ch in char_iter:
                if ch == '\n':
                    yield Token(Token.NEWLINE, '\n',
                                char_iter.location_from(pos))
                    break
        elif ch == '#':
            yield read_slice(char_iter, PLACEHOLDER_CHARS, Token.PLACEHOLDER,
                             start_pos=pos)
        elif ch == '\n' and not brackets:
            yield Token(Token.NEWLINE, '\n', char_iter.location_from(pos))
        elif ch == ' ':
            continue
        elif ch == '"':
            yield read_string(char_iter, pos, '"', errors)
        elif ch in ascii_letters or ch == DOT:
            yield read_slice(char_iter, SYMBOL_CHARS, Token.SYMBOL, pos)
        elif ch in digits:
            yield read_slice(char_iter, NUMBER_CHARS, Token.NUMBER, pos)
        elif ch in '([{':
            brackets.append((ch, pos))
            yield Token(BRACKET_TYPES[ch], ch, char_iter.location_from(pos))
        elif ch in '}])':
            if brackets:
                bch, bpos = brackets.pop()
                if MATCHING_BRACKET[bch] != ch:
                    with errors.location(char_iter.location_from(bpos)):
                        raise TokenizerError("Unmatching parenthesis, expected "
                                             "{!r} got {!r}"
                                             .format(MATCHING_BRACKET[bch], ch))
            else:
                with errors.location(char_iter.location_from(pos)):
                    raise TokenizerError("No parenthesis matching {!r}"
                                         .format(ch))
            yield Token(BRACKET_TYPES[ch], ch, char_iter.location_from(pos))
        else:
            # not using location_from to handle properly newline character
            loc = Location(pos, pos._replace(offset=pos.offset+1,
                                             column=pos.column+1))
            with errors.location(loc):
                raise TokenizerError("Wrong character {!r}".format(ch))
    else:
        eof_pos = char_iter.location_from(char_iter.next_position)
        if char_iter.next_position.column != 1:
            yield Token(Token.NEWLINE, '\n', eof_pos)
    eof_pos = char_iter.location_from(char_iter.next_position)
    if brackets:
        bch, bpos = brackets[-1]
        with errors.location(char_iter.location_from(bpos)):
            raise TokenizerError("Not closed parenthesis")
    for i in range(1, len(indents)):
        yield Token(Token.DEDENT, '', eof_pos)
    yield Token(Token.EOF, '', eof_pos)
