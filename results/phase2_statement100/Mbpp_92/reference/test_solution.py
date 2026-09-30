from solution import *


def test_reference_1():
    assert is_undulating(1212121) == True

def test_reference_2():
    assert is_undulating(1991) == False

def test_reference_3():
    assert is_undulating(121) == True
