import hashlib

def generate_sha512(input_string):
    # Create a sha512 hash object
    sha512_hash = hashlib.sha512()

    # Update the hash object with the bytes of the input string
    sha512_hash.update(input_string.encode('utf-8'))

    # Return the hexadecimal representation of the hash
    return sha512_hash.hexdigest()