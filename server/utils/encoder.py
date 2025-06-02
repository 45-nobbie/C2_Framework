import base64

class DataEncoder:
    """
    Handles encoding and decoding of C2 data for DNS tunneling.
    Uses Base64 for safe transmission over DNS.
    """

    @staticmethod
    def encode(data: str) -> str:
        """
        Encodes a string into Base64.
        Returns the Base64 encoded string, safe for DNS names (after further processing if needed).
        """
        # Encode to bytes, then base64 encode, then decode to string for URL-safe representation
        encoded_bytes = base64.urlsafe_b64encode(data.encode('utf-8'))
        return encoded_bytes.decode('utf-8').strip('=') # .strip('=') removes padding which is often optional and can save space

    @staticmethod
    def decode(encoded_data: str) -> str:
        """
        Decodes a Base64 string back to its original form.
        Re-adds padding if necessary before decoding.
        """
        # Add back padding if removed (Base64 requires padding to be a multiple of 4)
        missing_padding = len(encoded_data) % 4
        if missing_padding:
            encoded_data += '=' * (4 - missing_padding)

        decoded_bytes = base64.urlsafe_b64decode(encoded_data.encode('utf-8'))
        return decoded_bytes.decode('utf-8')

# Example usage for testing
if __name__ == "__main__":
    original_data = "Hello, this is a secret command payload! And some special chars: !@#$%^&*()"
    print(f"Original: {original_data}")

    encoded_data = DataEncoder.encode(original_data)
    print(f"Encoded:  {encoded_data}")

    decoded_data = DataEncoder.decode(encoded_data)
    print(f"Decoded:  {decoded_data}")

    assert original_data == decoded_data
    print("\nEncoding/Decoding test passed!")

    # Test with typical DNS constraints: lowercase and max length (not strictly enforced here yet)
    # DNS labels are usually 63 chars max, full name 255.
    # Our data will be split into multiple labels.
    long_data = "A" * 100
    encoded_long = DataEncoder.encode(long_data)
    print(f"\nLong data encoded length: {len(encoded_long)}")
    print(f"Decoded long data: {DataEncoder.decode(encoded_long)[:10]}...") # Show first 10 chars