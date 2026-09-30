from solution import is_woodall

def test_is_woodall_positive_woodall():
    assert is_woodall(383) == True

def test_is_woodall_non_positive():
    assert is_woodall(0) == False
    assert is_woodall(-5) == False

def test_is_woodall_not_woodall():
    assert is_woodall(10) == False

def test_is_woodall_edge_case():
    assert is_woodall(1) == True

def test_is_woodall_large_non_woodall():
    assert is_woodall(1000) == False

def test_is_woodall_another_woodall():
    assert is_woodall(7) == True
