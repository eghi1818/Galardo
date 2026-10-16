"""GALARDO - tangga verifikasi kepemilikan target (Fase A: universalitas Goal 1).

Masalah
-------
GATE 0 fail-closed: target harus VERIFIED sebelum ada traffic. Tapi satu-satunya
jalur verifikasi adalah TXT DNS, dan itu hanya bisa dipasang di zona yang kita
kontrol. Untuk situs pihak ketiga, satu-satunya jalan keluar adalah
GALARDO_LOCAL_DEV=1 -- "percaya operator", bukan bukti.

Tangga
------
Empat rung, masing-masing dengan tingkat kekuatan EKSPLISIT:

    rank 4  dns_txt               bukti; butuh akses zona DNS
    rank 3  well_known_file       bukti; butuh akses deploy berkas
    rank 2  http_echo             bukti; butuh akses ubah header/meta
    rank 1  operator_attestation  BUKAN bukti; selalu berlabel + berbatas waktu

Level minimum WAJIB dipilih eksplisit (fail-closed). Kalau min_level tidak
dikenali, verifikasi dianggap tidak cukup -- tidak ada default diam-diam.

Python 3.9, stdlib only.
"""

from __future__ import annotations

import hashlib
import secrets
import time
import urllib.error
import urllib.request

__all__ = [
    "LEVELS", "LEVEL_RANK", "LEVEL_IS_PROOF", "DEFAULT_ATTEST_TTL",
    "WELL_KNOWN_TEMPLATE", "ECHO_HEADER", "ECHO_META_TEMPLATE", "VALUE_TEMPLATE",
    "LadderError", "LadderProof", "WellKnownChallenge", "EchoChallenge",
    "OwnershipLadder", "verify_well_known", "verify_http_echo", "attest",
    "default_fetcher", "level_at_least", "adapt_dns_proof",
]

LEVELS = ("dns_txt", "well_known_file", "http_echo", "operator_attestation")
LEVEL_RANK = {"dns_txt": 4, "well_known_file": 3, "http_echo": 2,
              "operator_attestation": 1}
LEVEL_IS_PROOF = {"dns_txt": True, "well_known_file": True, "http_echo": True,
                  "operator_attestation": False}

DEFAULT_ATTEST_TTL = 24 * 3600
WELL_KNOWN_TEMPLATE = "/.well-known/galardo-{token}.txt"
ECHO_HEADER = "x-galardo-verify"
ECHO_META_TEMPLATE = '<meta name="galardo-verify" content="{token}">'
VALUE_TEMPLATE = "galardo-verify={account}:{token}"


class LadderError(Exception):
    """Konfigurasi atau pemakaian tangga tidak valid."""


def level_at_least(method, min_level):
    """True kalau `method` sekurang-kurangnya sekuat `min_level`."""
    need = LEVEL_RANK.get(min_level)
    got = LEVEL_RANK.get(method)
    if need is None or got is None:
        return False
    return got >= need


def _clean_domain(domain):
    d = str(domain).strip().lower().strip(".")
    if not d or "." not in d:
        raise LadderError("bukan domain yang layak: %r" % (domain,))
    return d


def _new_token():
    return "glr-%s" % secrets.token_hex(12)


def default_fetcher(url, timeout=6.0, max_bytes=131072):
    """fetcher(url, timeout) -> {"status", "headers", "body", "error"}.

    status 0 berarti koneksi gagal (bukan HTTP error). Tidak pernah melempar.
    """
    req = urllib.request.Request(
        url, method="GET",
        headers={"User-Agent": "galardo-ownership-ladder/1.0", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(max_bytes)
            headers = dict((k.lower(), v) for k, v in resp.headers.items())
            code = getattr(resp, "status", None) or resp.getcode()
            return {"status": int(code), "headers": headers, "body": body,
                    "error": None}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read(max_bytes)
        except Exception:
            body = b""
        headers = dict((k.lower(), v) for k, v in (exc.headers or {}).items())
        return {"status": int(exc.code), "headers": headers, "body": body,
                "error": None}
    except Exception as exc:
        return {"status": 0, "headers": {}, "body": b"", "error": str(exc)[:200]}


class LadderProof(object):
    """Hasil verifikasi satu rung. JSON-serialisable."""

    def __init__(self, ok, method, domain, account_id, token=None,
                 evidence=None, expires_at=None, detail=None, min_level=None):
        self.ok = bool(ok)
        self.method = method
        self.domain = str(domain)
        self.account_id = str(account_id)
        self.token = token
        self.evidence = evidence or {}
        self.expires_at = expires_at
        self.detail = detail
        self.min_level = min_level
        self.at = time.time()

    @property
    def rank(self):
        return LEVEL_RANK.get(self.method, 0)

    @property
    def is_proof(self):
        return bool(LEVEL_IS_PROOF.get(self.method, False))

    def sufficient(self, min_level=None):
        if not self.ok:
            return False
        return level_at_least(self.method, min_level or self.min_level)

    def expired(self, now=None):
        if self.expires_at is None:
            return False
        return (now or time.time()) >= self.expires_at

    def fingerprint(self):
        material = "|".join([self.domain, self.method, self.token or "",
                             "1" if self.ok else "0"])
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def to_dict(self):
        return {
            "ok": self.ok,
            "method": self.method,
            "rank": self.rank,
            "is_proof": self.is_proof,
            "domain": self.domain,
            "account_id": self.account_id,
            "token": self.token,
            "expires_at": self.expires_at,
            "expired": self.expired(),
            "detail": self.detail,
            "min_level": self.min_level,
            "evidence": self.evidence,
            "fingerprint": self.fingerprint(),
            "at": self.at,
        }

    def __repr__(self):
        return "<LadderProof ok=%s method=%s domain=%s>" % (
            self.ok, self.method, self.domain)


class _BaseChallenge(object):
    def __init__(self, domain, account_id, token=None, base_url=None,
                 created_at=None):
        self.domain = _clean_domain(domain)
        self.account_id = str(account_id)
        self.token = token or _new_token()
        self.base_url = base_url
        self.created_at = created_at or time.time()

    @property
    def root(self):
        return (self.base_url or ("https://" + self.domain)).rstrip("/")

    def to_dict(self):
        return {"domain": self.domain, "account_id": self.account_id,
                "token": self.token, "base_url": self.base_url,
                "created_at": self.created_at}


class WellKnownChallenge(_BaseChallenge):
    """Rung 2: berkas di /.well-known/."""

    @property
    def path(self):
        return WELL_KNOWN_TEMPLATE.format(token=self.token)

    @property
    def url(self):
        return self.root + self.path

    @property
    def expected_value(self):
        return VALUE_TEMPLATE.format(account=self.account_id, token=self.token)

    def instructions(self):
        return ("Simpan berkas ini di server target:",
                "  URL   : %s" % self.url,
                "  Isi   : %s" % self.expected_value,
                "  Status: 200, content-type text/plain")


class EchoChallenge(_BaseChallenge):
    """Rung 3: token dipantulkan di header atau meta halaman utama."""

    @property
    def url(self):
        return self.root + "/"

    @property
    def header_name(self):
        return "X-Galardo-Verify"

    @property
    def meta_tag(self):
        return ECHO_META_TEMPLATE.format(token=self.token)

    def instructions(self):
        return ("Pantulkan token di halaman utama target:",
                "  Header: %s: %s" % (self.header_name, self.token),
                "  ATAU meta: %s" % self.meta_tag)


def _decode(body):
    if isinstance(body, bytes):
        return body.decode("utf-8", "replace")
    return body or ""


def verify_well_known(challenge, fetcher=None, timeout=6.0):
    """Rung 2. Selalu mengembalikan LadderProof, tidak pernah melempar."""
    f = fetcher or default_fetcher
    try:
        r = f(challenge.url, timeout) or {}
    except Exception as exc:
        return LadderProof(False, "well_known_file", challenge.domain,
                           challenge.account_id, token=challenge.token,
                           evidence={"url": challenge.url, "error": str(exc)[:200]},
                           detail="fetcher melempar")
    status = r.get("status")
    body = _decode(r.get("body"))
    found = challenge.token in body
    ok = (status == 200) and found
    return LadderProof(
        ok, "well_known_file", challenge.domain, challenge.account_id,
        token=challenge.token,
        evidence={"url": challenge.url, "status": status, "token_found": found,
                  "error": r.get("error")},
        detail=None if ok else ("status=%s token_found=%s" % (status, found)))


def verify_http_echo(challenge, fetcher=None, timeout=6.0):
    """Rung 3. Selalu mengembalikan LadderProof, tidak pernah melempar."""
    f = fetcher or default_fetcher
    try:
        r = f(challenge.url, timeout) or {}
    except Exception as exc:
        return LadderProof(False, "http_echo", challenge.domain,
                           challenge.account_id, token=challenge.token,
                           evidence={"url": challenge.url, "error": str(exc)[:200]},
                           detail="fetcher melempar")
    status = r.get("status")
    headers = r.get("headers") or {}
    body = _decode(r.get("body"))
    in_header = challenge.token in (headers.get(ECHO_HEADER) or "")
    in_body = challenge.token in body
    ok = (status == 200) and (in_header or in_body)
    return LadderProof(
        ok, "http_echo", challenge.domain, challenge.account_id,
        token=challenge.token,
        evidence={"url": challenge.url, "status": status,
                  "in_header": in_header, "in_body": in_body,
                  "error": r.get("error")},
        detail=None if ok else ("status=%s in_header=%s in_body=%s"
                                % (status, in_header, in_body)))


def attest(domain, account_id, ttl_seconds=DEFAULT_ATTEST_TTL, note="", now=None):
    """Rung 4. BUKAN bukti -- selalu berlabel dan berbatas waktu."""
    base = now or time.time()
    return LadderProof(
        True, "operator_attestation", domain, account_id,
        evidence={"note": note, "declared_by": str(account_id)},
        expires_at=base + ttl_seconds,
        detail="attestasi operator; bukan bukti kriptografis")


def adapt_dns_proof(own_proof, domain, account_id):
    """Ubah ownership.Proof (TXT DNS) menjadi LadderProof rank 4."""
    ok = bool(getattr(own_proof, "ok", False))
    return LadderProof(
        ok, "dns_txt", domain, account_id,
        token=getattr(own_proof, "token", None),
        evidence=getattr(own_proof, "evidence", {}) or {},
        detail=("label=%s" % getattr(own_proof, "label", None)) if ok
               else "quorum TXT belum terpenuhi")


class OwnershipLadder(object):
    """Orkestrasi rung. min_level WAJIB dan eksplisit."""

    def __init__(self, min_level, fetcher=None, timeout=6.0,
                 attest_ttl=DEFAULT_ATTEST_TTL, dns_verifier=None):
        if min_level not in LEVELS:
            raise LadderError("min_level asing: %r (pilih dari %s)"
                              % (min_level, list(LEVELS)))
        self.min_level = min_level
        self.fetcher = fetcher
        self.timeout = timeout
        self.attest_ttl = attest_ttl
        self.dns_verifier = dns_verifier

    def verify(self, challenge, method):
        if method == "well_known_file":
            p = verify_well_known(challenge, self.fetcher, self.timeout)
        elif method == "http_echo":
            p = verify_http_echo(challenge, self.fetcher, self.timeout)
        elif method == "operator_attestation":
            p = attest(challenge.domain, challenge.account_id,
                       self.attest_ttl)
        elif method == "dns_txt":
            if self.dns_verifier is None:
                raise LadderError("method dns_txt butuh dns_verifier")
            p = adapt_dns_proof(self.dns_verifier(challenge),
                                challenge.domain, challenge.account_id)
        else:
            raise LadderError("method asing: %r" % (method,))
        p.min_level = self.min_level
        return p

    def run(self, challenges, methods=("well_known_file", "http_echo")):
        """Coba rung berurutan; kembalikan yang pertama berhasil.

        Kalau semua gagal, kembalikan yang terakhir dicoba supaya bukti
        kegagalan tetap terbawa (bukan None).
        """
        last = None
        for method in methods:
            ch = challenges.get(method)
            if ch is None:
                continue
            last = self.verify(ch, method)
            if last.ok:
                return last
        if last is not None:
            return last
        return LadderProof(False, methods[0], "?", "?", detail="tidak ada challenge")

    def gate(self, proof):
        """Fail-closed: cukup atau tidak, plus alasan yang bisa diaudit."""
        if not proof.ok:
            return False, "verifikasi gagal (%s): %s" % (proof.method, proof.detail)
        if proof.expired():
            return False, "bukti kedaluwarsa (%s)" % proof.method
        if not proof.sufficient(self.min_level):
            return False, ("tingkat bukti %s (rank %d) di bawah minimum %s (rank %d)"
                           % (proof.method, proof.rank, self.min_level,
                              LEVEL_RANK.get(self.min_level, 0)))
        return True, "cukup: %s rank %d >= min %s" % (
            proof.method, proof.rank, self.min_level)
