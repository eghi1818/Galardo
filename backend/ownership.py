"""DNS TXT ownership challenge.

Galardo must not hammer a domain it does not control. Before a target can be
promoted from "discovered" to "active", the operator proves control by
publishing a token in a TXT record. Two labels are accepted:

* ``_galardo.<domain>`` -- current
* ``_galodo.<domain>``  -- legacy, for domains set up before the rename

Verification requires a quorum across independent resolvers, so a single
hijacked or stale resolver cannot approve a target.

Python 3.9 compatible.
"""

from __future__ import annotations

import hashlib
import secrets
import time

try:
    from . import netdns
except ImportError:
    import netdns

__all__ = [
    "PRIMARY_LABEL", "LEGACY_LABEL", "DEFAULT_LABELS", "CHALLENGE_TTL",
    "OwnershipError", "Challenge", "Proof", "OwnershipVerifier",
    "new_token", "record_name",
]

PRIMARY_LABEL = "_galardo"
LEGACY_LABEL = "_galodo"
DEFAULT_LABELS = (PRIMARY_LABEL, LEGACY_LABEL)
CHALLENGE_TTL = 24 * 3600
VALUE_TEMPLATE = "galardo-verify={account}:{token}"

class OwnershipError(Exception):
    """Challenge could not be built or verified."""

def new_token(prefix="galardo"):
    return "%s-%s" % (prefix, secrets.token_hex(16))

def record_name(domain, label=PRIMARY_LABEL):
    return "%s.%s" % (label, str(domain).strip().strip("."))

def _clean_domain(domain):
    domain = str(domain).strip().lower().strip(".")
    if not domain or "." not in domain:
        raise OwnershipError("not a registrable domain: %r" % (domain,))
    return domain

class Challenge(object):
    """A pending proof-of-control. JSON serialisable."""

    def __init__(self, domain, account_id, token=None, label=PRIMARY_LABEL,
                 created_at=None, attempts=0, verified_at=None, proof=None):
        self.domain = _clean_domain(domain)
        self.account_id = str(account_id)
        self.token = token or new_token()
        self.label = label
        self.created_at = created_at or time.time()
        self.attempts = attempts
        self.verified_at = verified_at
        self.proof = proof

    @property
    def record_name(self):
        return record_name(self.domain, self.label)

    @property
    def expected_value(self):
        return VALUE_TEMPLATE.format(account=self.account_id, token=self.token)

    @property
    def ttl_seconds(self):
        return int(max(0, self.created_at + CHALLENGE_TTL - time.time()))

    def is_expired(self, now=None):
        return (now or time.time()) > self.created_at + CHALLENGE_TTL

    @property
    def verified(self):
        return self.verified_at is not None

    def bump(self):
        self.attempts += 1
        return self.attempts

    def to_dict(self):
        return {
            "domain": self.domain,
            "account_id": self.account_id,
            "token": self.token,
            "label": self.label,
            "record_name": self.record_name,
            "expected_value": self.expected_value,
            "created_at": self.created_at,
            "attempts": self.attempts,
            "verified_at": self.verified_at,
            "proof": self.proof,
        }

    @classmethod
    def from_dict(cls, document):
        return cls(
            document["domain"],
            document["account_id"],
            token=document.get("token"),
            label=document.get("label", PRIMARY_LABEL),
            created_at=document.get("created_at"),
            attempts=document.get("attempts", 0),
            verified_at=document.get("verified_at"),
            proof=document.get("proof"),
        )

    def instructions(self):
        return (
            "Tambah satu record DNS pada zona %s:" % self.domain,
            "  Tipe  : TXT",
            "  Nama  : %s" % self.record_name,
            "  Nilai : %s" % self.expected_value,
            "  TTL   : 300 (atau serendah yang diizinkan provider)",
            "Verifikasi butuh quorum 2 dari 3 resolver independen.",
        )

    def __repr__(self):
        return "<Challenge %s %s>" % (self.record_name, self.token)

class Proof(object):
    """Verification outcome. ``ok`` False keeps the target un-promoted."""

    def __init__(self, ok, challenge, label=None, record=None, evidence=None,
                 verified_at=None):
        self.ok = bool(ok)
        self.challenge = challenge
        self.label = label
        self.record = record
        self.evidence = evidence or {}
        self.verified_at = verified_at or (time.time() if ok else None)

    @property
    def token(self):
        return self.challenge.token

    @property
    def domain(self):
        return self.challenge.domain

    def fingerprint(self):
        material = "%s|%s|%s|%s" % (
            self.domain, self.record or "", self.token, self.ok)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {
            "ok": self.ok,
            "domain": self.domain,
            "label": self.label,
            "record": self.record,
            "token": self.token,
            "verified_at": self.verified_at,
            "evidence": self.evidence,
            "fingerprint": self.fingerprint(),
        }

    def __repr__(self):
        return "<Proof ok=%s %s>" % (self.ok, self.record)

class OwnershipVerifier(object):
    def __init__(self, resolvers=None, required=2, timeout=netdns.DEFAULT_TIMEOUT,
                 allow_doh=True, labels=DEFAULT_LABELS):
        self.resolvers = list(resolvers or netdns.DEFAULT_RESOLVERS)
        self.required = required
        self.timeout = timeout
        self.allow_doh = allow_doh
        self.labels = tuple(labels)

    def verify(self, challenge, labels=None):
        """Try each accepted label. Returns a Proof either way."""
        if challenge.is_expired():
            return Proof(False, challenge, evidence={"error": "challenge expired"})

        challenge.bump()
        attempts = {}
        for label in (labels or self.labels):
            name = record_name(challenge.domain, label)
            ok, evidence = netdns.txt_quorum(
                name, challenge.token, self.resolvers, self.required,
                self.timeout, self.allow_doh)
            attempts[label] = evidence
            if ok:
                challenge.verified_at = time.time()
                proof = Proof(True, challenge, label=label, record=name, evidence=evidence)
                challenge.proof = proof.to_dict()
                return proof

        return Proof(False, challenge, evidence={"attempts": attempts})

    def revoke(self, challenge):
        challenge.verified_at = None
        challenge.proof = None
        return challenge
