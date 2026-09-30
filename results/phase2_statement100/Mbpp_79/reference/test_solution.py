from solution import *


def test_reference_1():
    assert word_len("Hadoop") == False

def test_reference_2():
    assert word_len("great") == True

def test_reference_3():
    assert word_len("structure") == True
