#!/usr/bin/env python3
"""Validasi berkas skenario YAML terhadap policy. Pakai: python3 tools/validasi_skenario.py <berkas.yaml>"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEK = os.path.join(ROOT, "backend")

if len(sys.argv) < 2:
    print("pakai: python3 tools/validasi_skenario.py <berkas.yaml>")
    sys.exit(2)
berkas = os.path.abspath(sys.argv[1])
if not os.path.exists(berkas):
    print("berkas tidak ada: %s" % berkas)
    sys.exit(2)

os.chdir(BEK)
sys.path.insert(0, BEK)

import api as _a
_a.seed_lab()
from scenario import parse_scenario_yaml, ScenarioError
from policy import effective_policy, resolve_scenario_layers, validate_against_policy
import db


def main():
    targets = {t["name"]: t for t in db.list("targets")}
    teks = open(berkas, encoding="utf-8").read()
    try:
        norm = parse_scenario_yaml(teks, targets)
        tgt = db.get("targets", norm["target_id"])
        layers = resolve_scenario_layers(db, norm, engagement_id=tgt.get("engagement_id"))
        eff, _ = effective_policy(layers)
        errs = validate_against_policy(
            {"max_rps": norm["profile"]["max_rps"],
             "max_vus": norm["profile"]["virtual_users"],
             "max_duration_sec": norm["profile"]["duration_seconds"],
             "paths": norm["request_paths"]}, eff, tgt)
        if errs:
            print(json.dumps({"valid": False, "errors": errs}, indent=1))
            return 1
        print(json.dumps({"valid": True, "scenario_hash": norm["scenario_sha256"],
                          "effective_limits": {"max_rps": eff["max_rps"],
                                               "max_vus": eff["max_vus"],
                                               "max_duration_sec": eff["max_duration_sec"]}}, indent=1))
    except ScenarioError as e:
        print(json.dumps({"valid": False, "errors": e.errors}, indent=1))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
