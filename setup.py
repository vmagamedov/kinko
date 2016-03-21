from setuptools import setup, find_packages

setup(
    name='Kinko',
    version='0.1.dev0',
    description='Experimental frontend DSL',
    author='Vladimir Magamedov',
    author_email='vladimir@magamedov.com',
    url='https://github.com/vmagamedov/kinko',
    packages=find_packages(),
    license='BSD',
    install_requires=['funcparserlib', 'astor', 'markupsafe'],
    extras_require={
        'js': ['slimit'],
        'cli': ['click'],
        'html': ['lxml'],
    }
)
