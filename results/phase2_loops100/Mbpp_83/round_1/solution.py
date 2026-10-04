def get_Char(strr):
    total = sum(ord(c) for c in strr)
    result = total % 26
    return chr(result + ord('a'))
