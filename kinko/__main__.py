from collections import namedtuple

import click
import astor

from .parser import parser
from .checker import check, Environ
from .compiler import compile_module
from .tokenizer import tokenize


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
@click.argument('source', type=click.File(encoding='utf-8'))
@click.argument('output', type=click.File(mode='w+', encoding='utf-8'),
                default='-')
@click.pass_context
def compile_(ctx, source, output):
    try:
        tokens = list(tokenize(source.read()))
        node = parser().parse(tokens)
    except Exception:
        # TODO: print pretty parsing error
        click.echo('Failed to parse source file', err=True)
        maybe_exit(ctx, -1)
        raise

    try:
        # TODO: implement environ definition
        node = check(node, Environ({}))
    except TypeError:
        # TODO: print pretty type checking error
        click.echo('Failed to check source file', err=True)
        maybe_exit(ctx, -2)
        raise

    try:
        module = compile_module(node)
        compile(module, '<tmp>', 'exec')
    except Exception:
        click.echo('Failed to compile module. Please submit bug report.',
                   err=True)
        maybe_exit(ctx, -3)
        raise
    else:
        output.write(astor.to_source(module))
        output.write('\n')


if __name__ == '__main__':
    cli.main(prog_name='python -m kinko')
