from solution import *


def test_reference_1():
    assert len_log(["python","PHP","bigdata"]) == 7

def test_reference_2():
    assert len_log(["a","ab","abc"]) == 3

def test_reference_3():
    assert len_log(["small","big","tall"]) == 5
