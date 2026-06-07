from core.security import hash_passcode, verify_passcode


def test_hash_passcode():
    passcode = "mysecret123"
    hashed = hash_passcode(passcode)

    assert hashed != passcode
    assert len(hashed) > 0
    assert isinstance(hashed, str)

def test_verify_passcode():
    passcode = "securepass"
    hashed = hash_passcode(passcode)

    # Successful authentication
    assert verify_passcode(passcode, hashed) is True

    # Mismatched/incorrect passcode
    assert verify_passcode("wrongpass", hashed) is False

    # Incorrect hash format
    assert verify_passcode(passcode, "invalid_hash_format") is False

    # Exception handling (e.g. checkpw raising exceptions for invalid hash types like None)
    assert verify_passcode(passcode, None) is False
