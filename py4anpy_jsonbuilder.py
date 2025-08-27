#!/usr/bin/env python3
# make_mdatp_onboard_json.py

import argparse, ast, json, os, re, sys
from typing import Any, Dict, Tuple

TARGET_KEYS = {
    "service_principal_id",
    "subscription_id",
    "tenant_id",
    "azurelocation",
    "authType",
    "correlationId",
    "cloud",
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
]

# ---------- helpers ----------

def _safe_literal_from_ast(node: ast.AST, source: str) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.Dict, ast.List, ast.Tuple, ast.Set)):
        try:
            return ast.literal_eval(node)
        except Exception:
            pass
    if isinstance(node, ast.JoinedStr):
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
        if fn_name in {"get", "getenv"} and node.args:
            if len(node.args) >= 2:
                return _safe_literal_from_ast(node.args[1], source)
            return _safe_literal_from_ast(node.args[0], source)
    seg = ast.get_source_segment(source, node)
    return seg.strip() if isinstance(seg, str) else None

def _extract_with_ast(py_text: str) -> Dict[str, Any]:
    tree = ast.parse(py_text)
    out: Dict[str, Any] = {}
    cloud_props: Dict[str, Any] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
            if not targets:
                continue
            for t in targets:
                key = t.id
                care = (key in TARGET_KEYS) or (key in CLOUD_PROP_KEYS) or key.lower() == "cloud"
                if not care:
                    continue
                value_node = getattr(node, "value", None)
                if value_node is None:
                    continue
                value = _safe_literal_from_ast(value_node, py_text)
                if key in CLOUD_PROP_KEYS:
                    if isinstance(value, dict):
                        cloud_props.update(value)
                    else:
                        cloud_props[key] = value
                else:
                    out[key] = value
    if cloud_props:
        out["cloud_propagated"] = cloud_props
    return out

# --- tolerant regex/literal fallback for mixed files ---
_str_pat = r'"([^"]*)"|\'([^\']*)\''

def _grab_scalar(text: str, key: str) -> Any:
    # matches: key = "value" | key="value" | "key": "value"
    pat = re.compile(rf'(?i)\b{re.escape(key)}\b\s*[:=]\s*({_str_pat})')
    m = pat.search(text)
    if not m:
        return None
    return m.group(1) if m.group(1) is not None else m.group(2)

def _grab_object(text: str, key_variants) -> Tuple[str, str]:
    # find the first key variant followed by a JSON/Python-ish dict { ... } and return raw block
    for k in key_variants:
        m = re.search(rf'(?i)\b{k}\b\s*[:=]\s*\{{', text)
        if not m:
            continue
        start = m.end() - 1  # at the '{'
        # brace match
        depth = 0
        i = start
        while i < len(text):
            ch = text[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    block = text[start:i+1]
                    return k, block
            i += 1
    return "", ""

def _coerce_obj_literal(block: str) -> Dict[str, Any]:
    # try JSON first
    try:
        return json.loads(block)
    except Exception:
        pass
    # try Python literal (single quotes, trailing commas, etc.)
    try:
        return ast.literal_eval(block)
    except Exception:
        pass
    # last resort: loose fixes then JSON
    fixed = re.sub(r"'", '"', block)
    fixed = re.sub(r",\s*([\}\]])", r"\1", fixed)
    return json.loads(fixed)

def _extract_with_regex(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k in TARGET_KEYS:
        val = _grab_scalar(text, k)
        if val is not None:
            out[k] = val
    # cloud propagated dict
    key_used, block = _grab_object(text, CLOUD_PROP_KEYS)
    if block:
        try:
            out["cloud_propagated"] = _coerce_obj_literal(block)
        except Exception:
            out["cloud_propagated"] = {key_used: block}
    return out

# ---------- build & validate ----------

def build_mde_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "OrgId": data.get("tenant_id"),
        "SubscriptionId": data.get("subscription_id"),
        "ServicePrincipalId": data.get("service_principal_id"),
        "AuthType": data.get("authType"),
        "Location": data.get("azurelocation"),
        "CorrelationId": data.get("correlationId"),
    }
    if data.get("cloud"):
        payload["Cloud"] = data["cloud"]
    if isinstance(data.get("cloud_propagated"), dict):
        payload["CloudPropagatedParameters"] = data["cloud_propagated"]
    return payload

def validate_required(data: Dict[str, Any]) -> None:
    missing = []
    for src_key, label in REQUIRED_FOR_MDE:
        if not data.get(src_key):
            missing.append(f"{label} (source key '{src_key}')")
    if missing:
        raise SystemExit("ERROR: missing required onboarding fields:\n  - " + "\n  - ".join(missing))

# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description="Generate mdatp_onboard.json from a (possibly mixed) params script.")
    ap.add_argument("input_file", help="Path to generated params script (Python/mixed)")
    ap.add_argument("-o", "--out", default="/etc/opt/microsoft/mdatp/mdatp_onboard.json",
                    help="Output JSON (default: /etc/opt/microsoft/mdatp/mdatp_onboard.json)")
    ap.add_argument("--allow-missing", dest="allow_missing", action="store_true",
                    help="Do not error on missing required fields; write what we have")
    ap.add_argument("--print-only", dest="print_only", action="store_true",
                    help="Print JSON to stdout instead of writing to file")
    args = ap.parse_args()

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"ERROR: unable to read {args.input_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Try AST first; fall back to regex if we hit SyntaxError
    extracted: Dict[str, Any] = {}
    try:
        extracted = _extract_with_ast(text)
    except SyntaxError:
        extracted = _extract_with_regex(text)

    if not args.allow_missing:
        validate_required(extracted)

    payload = build_mde_payload(extracted)
    out_json = json.dumps(payload, indent=2)

    if args.print_only:
        print(out_json)
        return

    out_path = os.path.abspath(args.out)
    out_dir = os.path.dirname(out_path)
    os.makedirs(out_dir, exist_ok=True)
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out_json + "\n")
    except PermissionError:
        print(f"ERROR: permission denied writing {out_path}. Run with elevated privileges.", file=sys.stderr)
        sys.exit(1)
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    main()


# On the RHEL VM:
#sudo mv /path/to/mdatp_onboard.json /etc/opt/microsoft/mdatp/mdatp_onboard.json
#sudo mdatp onboarding --file /etc/opt/microsoft/mdatp/mdatp_onboard.json
#mdatp health --details | egrep "orgId|licensed|cloud"
