from cryptography.fernet import Fernet
from django.conf import settings

cipher = Fernet(settings.FERNET_KEY.encode())

def encrypt_file(data):
    return cipher.encrypt(data)

def decrypt_file(data):
    return cipher.decrypt(data)
