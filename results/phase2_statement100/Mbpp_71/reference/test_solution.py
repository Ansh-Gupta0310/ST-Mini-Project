from solution import *


def test_reference_1():
    assert comb_sort([5, 15, 37, 25, 79]) == [5, 15, 25, 37, 79]

def test_reference_2():
    assert comb_sort([41, 32, 15, 19, 22]) == [15, 19, 22, 32, 41]

def test_reference_3():
    assert comb_sort([99, 15, 13, 47]) == [13, 15, 47, 99]
