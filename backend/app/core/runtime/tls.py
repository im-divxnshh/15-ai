"""Verified TLS with system roots plus the bundled public CA certificates."""
import ssl
import certifi


def context():
    result=ssl.create_default_context()
    result.load_verify_locations(cafile=certifi.where())
    return result
