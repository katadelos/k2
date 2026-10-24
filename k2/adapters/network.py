"""TLS trust shared by device and desktop downloads."""

import ssl

import certifi


def tls_context():
    return ssl.create_default_context(cafile=certifi.where())
