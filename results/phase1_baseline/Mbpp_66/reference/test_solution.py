from solution import *


def test_reference_1():
    assert pos_count([1,-2,3,-4]) == 2

def test_reference_2():
    assert pos_count([3,4,5,-1]) == 3

def test_reference_3():
    assert pos_count([1,2,3,4]) == 4
