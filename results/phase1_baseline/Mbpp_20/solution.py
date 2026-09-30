def is_woodall(x):
    """
    Check if a number is a Woodall number.

    A Woodall number is a number of the form n * 2^n - 1, where n is a positive integer.

    Args:
        x (int): The number to check.

    Returns:
        bool: True if x is a Woodall number, False otherwise.
    """
    if x <= 0:
        return False
    n = 1
    while True:
        woodall = n * (1 << n) - 1  # n * 2^n - 1
        if woodall == x:
            return True
        if woodall > x:
            return False
        n += 1
