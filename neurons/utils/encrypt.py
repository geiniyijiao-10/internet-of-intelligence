import base64
import os
from datetime import datetime
from typing import Any, Dict
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


# -------------------------------
# struct_to_map
# -------------------------------
def struct_to_map(data: Any) -> Dict[str, str]:
    """
    Convert an object or dictionary into a key-value map.
    Skip the 'signature' field and convert supported types to string.
    """
    if isinstance(data, dict):
        items = data
    else:
        items = data.__dict__

    result = {}
    for k, v in items.items():
        if k == "signature":
            continue
        if isinstance(v, bool):
            result[k] = str(v).lower()
        elif isinstance(v, (int, float)):
            result[k] = str(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        elif v is not None:
            result[k] = str(v)
    return result


# -------------------------------
# map_to_sorted_query
# -------------------------------
def map_to_sorted_query(data: Dict[str, str]) -> str:
    """
    Convert a dictionary to a sorted query string.
    Example: {"b":2,"a":1} -> "a=1&b=2"
    """
    keys = sorted(data.keys())
    return "&".join(f"{k}={data[k]}" for k in keys)


# -------------------------------
# Encrypt (sign data)
# -------------------------------
def encrypt(data: Any, private_key: ed25519.Ed25519PrivateKey) -> str:
    """
    Sign the data using an Ed25519 private key and return a base64 signature.
    """
    data_map = struct_to_map(data)
    query = map_to_sorted_query(data_map)
    signature = private_key.sign(query.encode("utf-8"))
    return base64.b64encode(signature).decode("utf-8")


# -------------------------------
# Verify (verify signature)
# -------------------------------
def verify(data: Any, signature: str, public_key: ed25519.Ed25519PublicKey) -> bool:
    """
    Verify an Ed25519 signature.
    Returns True if valid, otherwise False.
    """
    data_map = struct_to_map(data)
    query = map_to_sorted_query(data_map)
    try:
        sig_bytes = base64.b64decode(signature)
        public_key.verify(sig_bytes, query.encode("utf-8"))
        return True
    except Exception:
        return False


# -------------------------------
# Generate public/private key pair
# -------------------------------
def generate_key():
    """
    Generate an Ed25519 public/private key pair.
    """
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    return public_key, private_key


# -------------------------------
# Save keys to files
# -------------------------------
def save_generate_key(private_path: str, public_path: str):
    """
    Generate and save Ed25519 public/private keys to files.
    Private key: permission 600
    Public key: permission 644
    """
    public_key, private_key = generate_key()

    os.makedirs(os.path.dirname(private_path), exist_ok=True)
    os.makedirs(os.path.dirname(public_path), exist_ok=True)

    # Save private key
    with open(private_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Save public key
    with open(public_path, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
        )


# -------------------------------
# Generate random nonce
# -------------------------------
def generate_nonce() -> str:
    """
    Generate a random 16-byte nonce encoded in Base64.
    """
    return base64.urlsafe_b64encode(os.urandom(16)).decode("utf-8")

# -------------------------------
# Read keys from files
# -------------------------------
def read_private_key(path: str) -> ed25519.Ed25519PrivateKey:
    """
    Read an Ed25519 private key from file.
    Supports:
        - Raw 32-byte private key (pure binary)
        - Go's 64-byte (private+public) format
        - PEM format ("-----BEGIN PRIVATE KEY-----")
        - OpenSSH format ("-----BEGIN OPENSSH PRIVATE KEY-----")
    """
    with open(path, "rb") as f:
        key_bytes = f.read()

    try:
        # Case 1: raw 32-byte key
        if len(key_bytes) == 32:
            return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes)

        # Case 2: Go-style 64-byte (private+public)
        if len(key_bytes) == 64:
            return ed25519.Ed25519PrivateKey.from_private_bytes(key_bytes[:32])

        # Case 3: PEM format
        if b"-----BEGIN" in key_bytes:
            return serialization.load_pem_private_key(key_bytes, password=None)

        # Case 4: OpenSSH format
        if b"OPENSSH" in key_bytes:
            return serialization.load_ssh_private_key(key_bytes, password=None)

        raise ValueError(f"Unsupported key format or length: {len(key_bytes)} bytes")

    except Exception as e:
        raise ValueError(f"Failed to parse Ed25519 private key: {e}")

# -------------------------------
# Read keys from files
# -------------------------------
def read_public_key(path: str) -> ed25519.Ed25519PublicKey:
    """
    Read an Ed25519 public key from a file.
    """
    with open(path, "rb") as f:
        key_bytes = f.read()
    return ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)


# -------------------------------
# Example usage
# -------------------------------
if __name__ == "__main__":
    # 1. Generate and save key pair
    save_generate_key("keys/private.key", "keys/public.key")

    # 2. Read keys
    priv = read_private_key("keys/private.key")
    pub = read_public_key("keys/public.key")

    # 3. Example data to sign
    data = {
        "name": "bittensor",
        "amount": 100,
        "timestamp": datetime.now(),
    }

    # 4. Sign data
    sig = encrypt(data, priv)
    print("Signature:", sig)

    # 5. Verify signature
    ok = verify(data, sig, pub)
    print("Verify result:", ok)