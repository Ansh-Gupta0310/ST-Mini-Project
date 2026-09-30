def is_undulating(n):
    s = str(n)
    if len(s) < 3:
        return False
    if len(set(s)) != 2:
        return False
    for i in range(len(s) - 2):
        if s[i] == s[i+1] or s[i+1] == s[i+2]:
            return False
    return True
