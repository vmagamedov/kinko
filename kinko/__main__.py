import io
import importlib
import subprocess
from collections import namedtuple

import click


def _get_osx_clipboard():
    p = subprocess.Popen(['pbpaste', '-Prefer', 'ascii'],
                         stdout=subprocess.PIPE)
    content, _ = p.communicate()
    return content.decode('utf-8')


class InputFile(click.File):

    def convert(self, value, param, ctx):
        if value == '@':
            content = _get_osx_clipboard()
            return io.StringIO(content)
        return super(InputFile, self).convert(value, param, ctx)


COMPILERS = {
    'py': 'kinko.out.py.compiler',
    'js': 'kinko.out.js.incremental_dom',
}


def maybe_exit(ctx, exit_code=-1):
    if not ctx.obj.debug:
        ctx.exit(exit_code)


GlobalOptions = namedtuple('GlobalOptions', 'verbose debug')


@click.group()
@click.option('-v', '--verbose', is_flag=True)
@click.option('--debug', is_flag=True)
@click.pass_context
def cli(ctx, verbose, debug):
    ctx.obj = GlobalOptions(verbose, debug)


@cli.command('compile')
@click.argument('type_', type=click.Choice(list(COMPILERS.keys())),
                metavar='TYPE')
@click.argument('source', type=click.File(encoding='utf-8'))
@click.argument('output', type=click.File(mode='w+', encoding='utf-8'),
                default='-')
@click.pass_context
def compile_(ctx, type_, source, output):
    from .parser import parser
    from .checker import check, Environ
    from .tokenizer import tokenize

    try:
        tokens = list(tokenize(source.read()))
        node = parser().parse(tokens)
    except Exception:
        # TODO: print pretty parsing error
        click.echo('Failed to parse source file.', err=True)
        maybe_exit(ctx)
        raise

    try:
        # TODO: implement environ definition
        node = check(node, Environ({}))
    except TypeError:
        # TODO: print pretty type checking error
        click.echo('Failed to check source file.', err=True)
        maybe_exit(ctx)
        raise

    compiler_path = COMPILERS[type_]
    try:
        compiler = importlib.import_module(compiler_path)
    except Exception:
        click.echo('Failed to load "{}" compiler.'.format(compiler_path),
                   err=True)
        maybe_exit(ctx)
        raise

    try:
        module = compiler.compile_module(node)
    except Exception:
        click.echo('Failed to compile module. Please submit bug report.',
                   err=True)
        maybe_exit(ctx)
        raise
    else:
        output.write(compiler.dumps(module))


@cli.command('convert')
@click.argument('input', type=InputFile(encoding='utf-8'))
@click.argument('output', type=click.File(mode='w+', encoding='utf-8'),
                default='-')
def convert(input, output):
    """To convert content from clipboard, pass `@` value as input (available
    only on OS X)."""
    from .converter import convert

    output.write(convert(input.read()))


if __name__ == '__main__':
    cli.main(prog_name='python -m kinko')
