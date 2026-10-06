"""Reviewer-hardening implementation for abstraction-sandwich certificates."""
from .checker import CertificateError, CheckResult, check_certificate_bytes, check_certificate_object


def __getattr__(name):
    # Importing a consumer submodule must not eagerly import the producer.
    # Preserve the convenience exports only when a producer API is requested.
    if name in {"Edge", "System", "build_quotient", "dense_value_table", "astar_witness",
                "ucs_witness", "exhaustive_oracle", "make_certificate"}:
        from . import core
        return getattr(core, name)
    raise AttributeError(name)

__all__ = [
    "Edge", "System", "build_quotient", "dense_value_table",
    "astar_witness", "ucs_witness", "exhaustive_oracle", "make_certificate",
    "CertificateError", "CheckResult", "check_certificate_bytes", "check_certificate_object",
]
