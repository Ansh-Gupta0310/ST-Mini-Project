from solution import is_woodall

def test_is_woodall_positive_woodall():
    assert is_woodall(383) == True

def test_is_woodall_negative_input():
    assert is_woodall(-5) == False

def test_is_woodall_zero():
    assert is_woodall(0) == False

def test_is_woodall_non_woodall_positive():
    assert is_woodall(10) == False

def test_is_woodall_next_woodall():
    assert is_woodall(2047) == True

def test_is_woodall_large_non_woodall():
    assert is_woodall(1000000) == False
