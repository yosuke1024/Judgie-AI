import bcrypt


def hash_passcode(passcode: str) -> str:
    """平文のパスコードをハッシュ化する"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(passcode.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_passcode(plain_passcode: str, hashed_passcode: str) -> bool:
    """平文のパスコードとハッシュ化されたパスコードが一致するか検証する"""
    try:
        return bcrypt.checkpw(plain_passcode.encode('utf-8'), hashed_passcode.encode('utf-8'))
    except Exception:
        return False
