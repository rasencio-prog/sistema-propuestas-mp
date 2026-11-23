from sp.core.crypto import decrypt, encrypt


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "ticket-de-prueba-123"
    ciphertext = encrypt(plaintext)

    assert ciphertext != plaintext.encode("utf-8")
    assert decrypt(ciphertext) == plaintext
