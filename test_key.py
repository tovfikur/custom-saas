from cryptography.fernet import Fernet
import base64

# Generate a proper Fernet key
key = Fernet.generate_key()
print(f"Generated key: {key.decode()}")
print(f"Key length: {len(key.decode())}")

# Test the key
try:
    f = Fernet(key)
    test_data = "test data"
    encrypted = f.encrypt(test_data.encode())
    decrypted = f.decrypt(encrypted).decode()
    print(f"Test successful: {test_data == decrypted}")
    print(f"Final key to use: {key.decode()}")
except Exception as e:
    print(f"Error: {e}")