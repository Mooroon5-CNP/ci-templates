#!/usr/bin/env python3
"""verify.py — run the CNP pipeline checks on each skeleton, locally, in Docker.

For every skeleton: render it (APP_NAME/APP_PORT), then run what pipeline.yml
runs on an application repo — the REAL detect-stack script (extracted from
pipeline.yml), lint, hadolint, test, gitleaks, trivy fs — and finally build the
image, start it, call /healthz, /ready and /, and trivy-scan the image.

The lint/test commands below mirror the `run:` steps of pipeline.yml; if the
pipeline changes, update COMMANDS (tests/test_skeletons.py reminds you by
checking that every command is still present in pipeline.yml).

Usage:  python skeletons/verify.py [lang ...] [--port 9090] [--log FILE] [--no-scan]
Needs:  Docker (Linux containers), Python 3 with PyYAML.
"""

import argparse
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PIPELINE = HERE.parent / ".github" / "workflows" / "pipeline.yml"
LANGS = ["node", "python", "go", "java", "cpp", "fullstack"]
APP_NAME = "demo-app"

IMAGES = {
    "node": "node:20", "python": "python:3.12", "go": "golang:1",
    "java": "maven:3.9-eclipse-temurin-21", "cpp": "ubuntu:24.04",
}
APT_CPP = "apt-get update -qq && apt-get install -y -qq cmake g++ make cppcheck >/dev/null"
COMMANDS = {
    "node": {
        "lint": "[ -f package-lock.json ] && npm ci --prefer-offline --silent && npm run lint",
        "test": "npm ci --prefer-offline --silent && npm test",
    },
    "python": {
        "lint": "pip install --quiet flake8 && flake8 .",
        "test": "[ -f requirements.txt ] && pip install --quiet -r requirements.txt; pip install --quiet pytest && pytest",
    },
    "go": {"lint": "go vet ./...", "test": "go test ./..."},
    "java": {"lint": "mvn -q -B compile", "test": "mvn -q -B test"},
    "cpp": {
        "lint": f"{APT_CPP} && cppcheck --error-exitcode=1 --quiet .",
        "test": f"{APT_CPP} && cmake -B build && cmake --build build && ctest --test-dir build --output-on-failure",
    },
}
# What detect-stack must find for each skeleton: (path, name, lang).
EXPECTED_TARGETS = {
    "node": [(".", "root", "node")], "python": [(".", "root", "python")],
    "go": [(".", "root", "go")], "java": [(".", "root", "java")],
    "cpp": [(".", "root", "cpp")],
    "fullstack": [("api", "api", "python"), ("web", "web", "node")],
}

LOG = []
RESULTS = []
CURRENT = [""]


def log(msg=""):
    print(msg, flush=True)
    LOG.append(msg)


def run(cmd, **kw):
    return subprocess.run(cmd, text=True, encoding="utf-8", errors="replace",
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kw)


def step(label, fn):
    start = time.time()
    try:
        ok, out = fn()
    except Exception as exc:  # noqa: BLE001 — a crashed step is a failed step
        ok, out = False, f"{type(exc).__name__}: {exc}"
    secs = time.time() - start
    lines = [ln for ln in (out or "").strip().splitlines() if "KiB /" not in ln and "MiB /" not in ln]
    log(f"  [{'PASS' if ok else 'FAIL'}] {label}  ({secs:.0f}s)")
    for line in lines[-(8 if ok else 60):]:
        log(f"        | {line}")
    RESULTS.append((f"{CURRENT[0]}: {label}", ok))
    return ok


def docker_run(image, script, workdir, extra=()):
    res = run(["docker", "run", "--rm", "-v", f"{workdir}:/w", "-w", "/w", *extra, image, "bash", "-ec", script])
    return res.returncode == 0, res.stdout


def render(lang, dest, port):
    for src in (HERE / "_common", HERE / lang):
        shutil.copytree(src, dest, dirs_exist_ok=True)
    for path in dest.rglob("*"):
        if path.is_file():
            data = path.read_bytes().decode("utf-8")
            path.write_bytes(data.replace("{{APP_NAME}}", APP_NAME).replace("{{APP_PORT}}", str(port)).encode("utf-8"))


def detect_targets(app):
    jobs = yaml.safe_load(PIPELINE.read_text(encoding="utf-8"))["jobs"]
    script = next(s["run"] for s in jobs["detect-stack"]["steps"] if s.get("id") == "detect")
    ok, out = docker_run("ubuntu:24.04",
                         "apt-get update -qq && apt-get install -y -qq jq >/dev/null && export GITHUB_OUTPUT=/tmp/o && " + script + "\ncat /tmp/o",
                         app)
    import json
    line = next((ln for ln in out.splitlines() if ln.startswith("matrix=")), None)
    if not ok or not line:
        return False, out, []
    targets = [(t["path"], t["name"], t["lang"]) for t in json.loads(line[len("matrix="):])["include"]]
    return True, f"Detected targets: {targets}", sorted(targets)


def free_port():
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def smoke(image, port):
    host = free_port()
    name = f"cnp-skel-{image.split(':')[0][-12:]}-{int(time.time())}"
    run(["docker", "rm", "-f", name])
    started = run(["docker", "run", "-d", "--name", name, "-p", f"{host}:{port}", image])
    if started.returncode != 0:
        return False, started.stdout
    try:
        out, deadline = [], time.time() + 40
        for path in ("/healthz", "/ready", "/"):
            while True:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{host}{path}", timeout=3) as r:
                        out.append(f"GET {path} -> {r.status} {r.read(200).decode('utf-8', 'replace')[:80]!r}")
                        if r.status != 200:
                            return False, "\n".join(out)
                        break
                except Exception as exc:  # noqa: BLE001
                    if time.time() > deadline:
                        out.append(f"GET {path} -> no answer ({exc})\n" + run(["docker", "logs", name]).stdout)
                        return False, "\n".join(out)
                    time.sleep(1)
        user = run(["docker", "inspect", "-f", "{{.Config.User}}", image]).stdout.strip()
        out.append(f"image user: {user or 'root'}")
        return user not in ("", "0", "root"), "\n".join(out)
    finally:
        run(["docker", "rm", "-f", name])


def verify(lang, port, scan):
    log(f"\n=== {lang} (APP_NAME={APP_NAME}, APP_PORT={port}) ===")
    tmp = Path(tempfile.mkdtemp(prefix=f"skel-{lang}-"))
    app = tmp / "app"
    try:
        render(lang, app, port)
        left = [p for p in app.rglob("*") if p.is_file() and b"{{" in p.read_bytes()
                and "node_modules" not in p.parts]
        step("render: no placeholder left, no workflow shipped",
             lambda: (not left and not (app / ".github").exists(), f"files: {sum(1 for p in app.rglob('*') if p.is_file())}  leftovers: {left}"))

        found = {}

        def do_detect():
            ok, out, targets = detect_targets(app)
            found["t"] = targets
            return ok and targets == sorted(EXPECTED_TARGETS[lang]), f"{out}\nexpected: {sorted(EXPECTED_TARGETS[lang])}"
        step("detect-stack (real script from pipeline.yml)", do_detect)

        for path, name, tlang in found.get("t", []):
            for kind in ("lint", "test"):
                step(f"{kind} [{name}/{tlang}]", lambda p=path, t=tlang, k=kind: docker_run(IMAGES[t], COMMANDS[t][k], str((app / p).resolve())))

        step("hadolint v2.14.0 (Dockerfile)", lambda: docker_run_plain(
            ["hadolint/hadolint:v2.14.0-alpine", "hadolint", "Dockerfile"], app))
        if scan:
            step("gitleaks (secrets)", lambda: docker_run_plain(
                ["zricethezav/gitleaks:latest", "detect", "--no-git", "--source=/w", "--redact", "--verbose"], app))
            step("trivy fs (CRITICAL blocking)", lambda: docker_run_plain(
                ["aquasec/trivy:latest", "fs", "--scanners", "vuln", "--severity", "CRITICAL", "--exit-code", "1",
                 "--ignore-unfixed", "--format", "table", "/w"], app))

        image = f"cnp-skel-{lang}:test"
        built = step("docker build", lambda: _ok(run(["docker", "build", "-q", "-t", image, str(app)])))
        if built:
            step(f"run image: /healthz /ready / answer 200 on {port}, non-root", lambda: smoke(image, port))
            if scan:
                step("trivy image (CRITICAL blocking)", lambda: _ok(run(
                    ["docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock", "aquasec/trivy:latest",
                     "image", "--severity", "CRITICAL", "--exit-code", "1", "--ignore-unfixed", "--format", "table", image])))
            run(["docker", "rmi", "-f", image])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _ok(res):
    return res.returncode == 0, res.stdout


def docker_run_plain(args, app):
    res = run(["docker", "run", "--rm", "-v", f"{app}:/w", "-w", "/w", *args])
    return res.returncode == 0, res.stdout


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("langs", nargs="*", default=LANGS)
    ap.add_argument("--port", type=int, default=9090, help="APP_PORT rendered into the skeleton (default 9090, to prove substitution)")
    ap.add_argument("--log", help="write the full report to this file")
    ap.add_argument("--no-scan", action="store_true", help="skip gitleaks and trivy (offline)")
    args = ap.parse_args()
    for lang in args.langs:
        verify(lang, args.port, not args.no_scan)
    failed = [label for label, ok in RESULTS if not ok]
    log(f"\nSUMMARY: {len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    for label in failed:
        log(f"  FAILED: {label}")
    if args.log:
        Path(args.log).write_text("\n".join(LOG) + "\n", encoding="utf-8")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
