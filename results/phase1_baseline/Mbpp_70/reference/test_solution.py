from solution import *


def test_reference_1():
    assert get_equal([(11, 22, 33), (44, 55, 66)]) == True

def test_reference_2():
    assert get_equal([(1, 2, 3), (4, 5, 6, 7)]) == False

def test_reference_3():
    assert get_equal([(1, 2), (3, 4)]) == True
