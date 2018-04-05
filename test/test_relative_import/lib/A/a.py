# lib/A/a.py

from ..B import b

def func():
    print("lib/A/a.py: func()")
    b.bar()
