from solution import *


def test_reference_1():
    assert recursive_list_sum(([1, 2, [3,4],[5,6]]))==21

def test_reference_2():
    assert recursive_list_sum(([7, 10, [15,14],[19,41]]))==106

def test_reference_3():
    assert recursive_list_sum(([10, 20, [30,40],[50,60]]))==210
