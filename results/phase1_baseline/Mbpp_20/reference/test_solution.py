from solution import *


def test_reference_1():
    assert is_woodall(383) == True

def test_reference_2():
    assert is_woodall(254) == False

def test_reference_3():
    assert is_woodall(200) == False
