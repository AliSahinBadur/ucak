"""cmc - CATIA Mass & CG pipeline.

Deterministic extraction of mass / centre-of-gravity / inertia from a running
CATIA V5 session, revision memory, and Adams/Car .cmd export.

The LLM agent driving this package must never compute numbers itself.
Every command prints a single JSON envelope on stdout; see cmc.envelope.
"""

__version__ = "1.0.0"
