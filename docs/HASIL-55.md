# HASIL-55 - P1.4 bukti e2e rung dns_txt (rank 4)

- Waktu (UTC) : 2026-10-16 13:19:42
- HEAD        : 79874fd
- Verdict     : OWN1_OK
- Domain      : koler.space
- Zone id     : 955743bd6a735db06701aa7f25932729
- Record TXT  : _galardo.koler.space
- Nilai       : galardo-verify=usr-verify:galardo-6c28dc96f2ec666b8e96d13bb777972a
- TXT pra-ada : 0
- Percobaan   : 8
- proof.ok    : True
- ladder      : method=dns_txt rank=4 is_proof=True
- gate        : True (cukup: dns_txt rank 4 >= min dns_txt)
- cleanup     : http=200 success=True

## proof.evidence
```json
{
 "qname": "_galardo.koler.space",
 "token": "galardo-6c28dc96f2ec666b8e96d13bb777972a",
 "required": 2,
 "ok_count": 2,
 "resolvers": {
  "1.1.1.1": {
   "ok": true,
   "rcode": 0,
   "matched": [
    "galardo-verify=usr-verify:galardo-6c28dc96f2ec666b8e96d13bb777972a"
   ]
  },
  "8.8.8.8": {
   "ok": false,
   "rcode": 3
  },
  "9.9.9.9": {
   "ok": true,
   "rcode": 0,
   "matched": [
    "galardo-verify=usr-verify:galardo-6c28dc96f2ec666b8e96d13bb777972a"
   ]
  }
 }
}
```

## log
```
== LIVE: rung dns_txt di koler.space ==
  token : cfut_0oM...16c1 (53)
  quorum: 1.1.1.1, 8.8.8.8, 9.9.9.9 (butuh 2 dari 3)
  GET /zones http=200 jumlah=1
  zone  : koler.space status=active id=955743bd6a735db06701aa7f25932729
  TXT   : _galardo.koler.space = galardo-verify=usr-verify:galardo-6c28dc96f2ec666b8e96d13bb777972a
  TXT pra-ada: 0
  POST ok record_id=235ec768920f94964e9fac8c61eb8b59
  resolusi 1/8 -> ok=False evidence={"attempts": {"_galardo": {"qname": "_galardo.koler.space", "token": "galardo-6c28dc96f2ec666b8e96d13bb777972a", "required": 2, "ok_count": 0, "resolvers": {"1.1.1.1": {"ok": false, "rcode": 3}, "8.8.
  resolusi 2/8 -> ok=False evidence={"attempts": {"_galardo": {"qname": "_galardo.koler.space", "token": "galardo-6c28dc96f2ec666b8e96d13bb777972a", "required": 2, "ok_count": 0, "resolvers": {"1.1.1.1": {"ok": false, "rcode": 3}, "8.8.
  resolusi 3/8 -> ok=True evidence={"qname": "_galardo.koler.space", "token": "galardo-6c28dc96f2ec666b8e96d13bb777972a", "required": 2, "ok_count": 2, "resolvers": {"1.1.1.1": {"ok": true, "rcode": 0, "matched": ["galardo-verify=usr-v
  LadderProof: method=dns_txt rank=4 is_proof=True
  gate: True (cukup: dns_txt rank 4 >= min dns_txt)
  cleanup: http=200 success=True
```
