# lib/A/__init__.py

from ..B import b  # ../B/b.py

from .. import B   # ../B/__init__.py

from . import a    # ./a.py

def foo():
    print("lib/A/__init__.py: foo()")
    print(B.V)
    b.bar()
    a.func()
    
