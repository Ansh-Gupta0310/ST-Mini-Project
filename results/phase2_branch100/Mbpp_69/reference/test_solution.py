from solution import *


def test_reference_1():
    assert is_sublist([2,4,3,5,7],[3,7])==False

def test_reference_2():
    assert is_sublist([2,4,3,5,7],[4,3])==True

def test_reference_3():
    assert is_sublist([2,4,3,5,7],[1,6])==False
