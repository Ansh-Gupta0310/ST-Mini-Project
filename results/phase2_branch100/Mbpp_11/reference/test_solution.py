from solution import *


def test_reference_1():
    assert remove_Occ("hello","l") == "heo"

def test_reference_2():
    assert remove_Occ("abcda","a") == "bcd"

def test_reference_3():
    assert remove_Occ("PHP","P") == "H"
