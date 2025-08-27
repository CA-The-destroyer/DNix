#!/usr/bin/env python3
"""
make_mdatp_onboard_json.py

Parse a generated Python params script and produce an MDE Linux onboarding JSON:
  /etc/opt/microsoft/mdatp/mdatp_onboard.json  (default output)

Fields extracted (case-sensitive as named in your script):
  - service_principal_id
  - subscription_id
  - tenant_id
  - azurelocation
  - authType
  - correlationId
  - cloud
  - cloudPropagatedParameters / cloud_propagated_parameters / cloud_propagated (merged)

Usage:
  sudo python make_mdatp_onboard_json.py /path/to/generated_params.py \
       --out /etc/opt/microsoft/mdatp/mdatp_onboard.json
"""

import argparse
import ast
import json
import os
import sys
from typing import Any, Dict

TARGET_KEYS = {
    "service_principal_id",
    "subscription_id",
    "tenant_id",
    "azurelocation",
    "authType",
    "correlationId",
    "cloud",
    "cloudPropagatedParameters",
    "cloud_propagated_parameters",
    "cloud_propagated",
}

CLOUD_PROP_KEYS = {
    "cloudPropagatedParameters",
    "cloud_propagated_parameters",
    "cloud_propagated",
    "propagated_parameters",
    "propagatedParams",
}

REQUIRED_FOR_MDE = [
    ("tenant_id", "OrgId"),
    ("subscription_id", "SubscriptionId"),
    ("service_principal_id", "ServicePrincipalId"),
    ("authType", "AuthType"),
    ("azurelocation", "Location"),
    ("correlationId", "CorrelationId"),
    # "cloud" is optional but good to have; cloud_propagated is optional
]


def _safe_literal(node: ast.AST, source: str) -> Any:
    """Best-effort extraction of a literal-ish value from AST."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
        try:
            return ast.literal_eval(node)
        except Exception:
            pass
    if isinstance(node, ast.JoinedStr):  # f-string
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant):
                parts.append(str(v.value))
            else:
                seg = ast.get_source_segment(source, v)
                parts.append(f"{{{seg}}}")
        return "".join(parts)
    if isinstance(node, ast.Call):
        fn = node.func
        fn_name = ""
        if isinstance(fn, ast.Attribute):
            fn_name = fn.attr or ""
        elif isinstance(fn, ast.Name):
            fn_name = fn.id or ""
        # Handle env getters like os.getenv("FOO","default") or dict.get("FOO","def")
        if fn_name in {"get", "getenv"} and node.args:
            if len(node.args) >= 2:
                return _safe_literal(node.args[1], source)
            return _safe_literal(node.args[0], source)
    seg = ast.get_source_segment(source, node)
    return seg.strip() if isinstance(seg, str) else None


def extract_params(py_text: str) -> Dict[str, Any]:
    tree = ast.parse(py_text)
    out: Dict[str, Any] = {}
    cloud_props: Dict[str, Any] = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            # collect target names
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]

            if not targets:
                continue

            for t in targets:
                key = t.id
                if (key not in TARGET_KEYS) and (key not in CLOUD_PROP_KEYS) and key.lower() not in {"cloud"}:
                    continue
                value_node = getattr(node, "value", None)
                if value_node is None:
                    continue

                value = _safe_literal(value_node, py_text)

                if key in CLOUD_PROP_KEYS:
                    if isinstance(value, dict):
                        cloud_props.update(value)
                    else:
                        # capture non-dict as-is under a namespaced key
                        cloud_props[key] = value
                    continue

                out[key] = value

    if cloud_props:
        out["cloud_propagated"] = cloud_props

    return out


def build_mde_onboard_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "OrgId": data.get("tenant_id"),
        "SubscriptionId": data.get("subscription_id"),
        "ServicePrincipalId": data.get("service_principal_id"),
        "AuthType": data.get("authType"),
        "Location": data.get("azurelocation"),
        "CorrelationId": data.get("correlationId"),
    }
    # Optional
    if "cloud" in data and data["cloud"]:
        payload["Cloud"] = data["cloud"]
    if "cloud_propagated" in data and isinstance(data["cloud_propagated"], dict):
        payload["CloudPropagatedParameters"] = data["cloud_propagated"]
    return payload


def validate_required(data: Dict[str, Any]) -> None:
    missing = []
    for src_key, label in REQUIRED_FOR_MDE:
        if not data.get(src_key):
            missing.append(f"{label} (source key '{src_key}')")
    if missing:
        raise SystemExit(
            "ERROR: missing required onboarding fields:\n  - " + "\n  - ".join(missing)
        )


def main():
    ap = argparse.ArgumentParser(description="Generate mdatp_onboard.json from a Python params script.")
    ap.add_argument("input_py", help="Path to generated Python script containing the parameters")
    ap.add_argument("-o", "--out", default="/etc/opt/microsoft/mdatp/mdatp_onboard.json",
                    help="Output JSON file (default: /etc/opt/microsoft/mdatp/mdatp_onboard.json)")
    ap.add_argument("--allow-missing", action="store_true",
                    help="Do not error on missing required fields; write what we have")
    ap.add_argument("--print-only", action="store_true",
                    help="Print JSON to stdout instead of writing to file")
    args = ap.parse_args()

    try:
        with open(args.input_py, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as e:
        print(f"ERROR: unable to read {args.input_py}: {e}", file=sys.stderr)
        sys.exit(1)

    extracted = extract_params(src)

    if not args.allow-missing:
        validate_required(extracted)

    payload = build_mde_onboard_payload(extracted)
    out_json = json.dumps(payload, indent=2)

    if args.print_only:
        print(out_json)
        return

    # Ensure directory exists (commonly /etc/opt/microsoft/mdatp)
    out_dir = os.path.dirname(os.path.abspath(args.out))
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception as e:
        print(f"ERROR: unable to create directory {out_dir}: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(out_json + "\n")
    except PermissionError:
        print(f"ERROR: permission denied writing {args.out}. Try running with sudo.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: unable to write {args.out}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()




# 1) Run it against your generated Python params file
#sudo python make_mdatp_onboard_json.py /path/to/generated_params.py \
 # --out /etc/opt/microsoft/mdatp/mdatp_onboard.json

# 2) Onboard Defender for Endpoint with that JSON
#sudo mdatp onboarding --file /etc/opt/microsoft/mdatp/mdatp_onboard.json

# 3) Verify
#mdatp health --details | egrep "orgId|licensed|cloud"
