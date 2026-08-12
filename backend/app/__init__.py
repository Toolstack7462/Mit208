"""PhishGuard backend application package."""

# The API's own contract version, and the single place it is defined: main.py reads
# it for the OpenAPI document, GET / and GET /health.
#
# This is deliberately NOT the Git release tag. The tag marks a state of the whole
# repository — report, evidence and documentation included — and moves when any of
# those change. This number describes the shape of the HTTP API, so it should move
# only when a client would notice. Tying the two together would announce an API
# change every time a figure caption was corrected.
__version__ = "1.0.0"
