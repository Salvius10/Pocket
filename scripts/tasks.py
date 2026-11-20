"""One task runner for every platform. `make <target>` and `./make.ps1 <target>` both call this.

Usage: uv run python scripts/tasks.py <target> [args...]
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "apps" / "mobile"
CORE = ROOT / "services" / "core_api"
PY_DIRS = ["packages/pocket_common", "services", "evals", "scripts"]


def flutter() -> str:
    """Flutter from PATH, FLUTTER_ROOT, or the default install location used on this project."""
    exe = "flutter.bat" if os.name == "nt" else "flutter"
    found = shutil.which("flutter")
    if found:
        return found
    for base in (os.environ.get("FLUTTER_ROOT"), str(Path.home() / "dev" / "flutter")):
        if base and (Path(base) / "bin" / exe).exists():
            return str(Path(base) / "bin" / exe)
    sys.exit("Flutter not found. Install it or set FLUTTER_ROOT.")


def run(cmd: list[str], cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("$", " ".join(cmd), flush=True)
    result = subprocess.run(cmd, cwd=cwd, env={**os.environ, "PYTHONIOENCODING": "utf-8", **(env or {})})
    if result.returncode != 0:
        sys.exit(result.returncode)


def dart_defines() -> list[str]:
    keys = ("API_BASE", "AGENT_BASE", "FIREBASE_API_KEY", "FIREBASE_APP_ID", "FIREBASE_PROJECT_ID", "FIREBASE_AUTH_DOMAIN", "FIREBASE_MESSAGING_SENDER_ID")
    return [f"--dart-define={k}={os.environ[k]}" for k in keys if os.environ.get(k)]


def setup() -> None:
    run(["uv", "sync", "--all-packages", "--all-extras"])
    run([flutter(), "pub", "get"], MOBILE)


def migrate() -> None:
    run(["uv", "run", "alembic", "upgrade", "head"], CORE)


def dev() -> None:
    """Both services with auto-reload. core-api :8080, agent :8081."""
    migrate()
    common = ["--reload", "--reload-dir", "packages/pocket_common"]
    procs = [
        subprocess.Popen(["uv", "run", "uvicorn", "core_api.main:app", "--port", "8080", *common, "--reload-dir", "services/core_api"], cwd=ROOT),
        subprocess.Popen(["uv", "run", "uvicorn", "agent.main:app", "--port", "8081", *common, "--reload-dir", "services/agent"], cwd=ROOT),
    ]
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()


def seed_demo() -> None:
    """Link all six personas to dev users and print their headline numbers."""
    run(["uv", "run", "python", "evals/smoke_core.py"])


def funds() -> None:
    print("data/reference/funds.csv ships with the v1 dataset (16 real Direct-Growth schemes, real latest NAV from AMFI).")
    print("NIFTY_PROXY_SCHEME_CODE defaults to 120716 (UTI Nifty 50 Index Fund - Direct Growth).")


def sms_variants() -> None:
    print("SMS wording variants ship with the v1 dataset (template ids ending .v3 are the held-out ones).")
    print("Regenerate the dataset with: cd packages/pocket_synth && python -m pocket_synth.export --out ../../data-out")


def lint() -> None:
    run(["uv", "run", "ruff", "check", *PY_DIRS])
    run([flutter(), "analyze", "--no-fatal-infos"], MOBILE)


def typecheck() -> None:
    run(["uv", "run", "mypy", "packages/pocket_common/pocket_common", "services/core_api/core_api", "services/agent/agent"])


def test() -> None:
    run(["uv", "run", "pytest"])
    where = _android_build_dir()  # same OneDrive problem as Gradle: Flutter cannot clear build/ there
    run([flutter(), "test"], where, env={"POCKET_FIXTURES": str(ROOT / "data" / "fixtures")})


def l10n() -> None:
    run([flutter(), "gen-l10n", "--arb-dir", "lib/l10n", "--template-arb-file", "app_en.arb", "--output-localization-file", "app_localizations.dart",
         "--output-class", "L", "--no-nullable-getter"], MOBILE)


def app() -> None:
    run([flutter(), "run", "-d", "chrome", *dart_defines()], MOBILE)


def web() -> None:
    """Release web build into apps/mobile/build/web (what Firebase Hosting publishes)."""
    # --no-web-resources-cdn: ship CanvasKit with the app so the judge link does not wait on a third-party CDN.
    target = MOBILE / "build" / "web"
    staging = target
    if os.name == "nt" and "onedrive" in str(MOBILE).lower():
        # OneDrive locks the build folder while Flutter rewrites it: build elsewhere, then copy in.
        staging = Path(os.environ.get("POCKET_WEB_OUT") or Path.home() / "dev" / "pocket-web-deploy")
    run([flutter(), "build", "web", "--release", "--no-web-resources-cdn", "--no-wasm-dry-run", "-o", str(staging), *dart_defines()], MOBILE)
    if staging != target:
        shutil.rmtree(target, ignore_errors=True)
        shutil.copytree(staging, target)
    print(f"web build: {target}")


def _android_build_dir() -> Path:
    """Where Gradle runs. A OneDrive-synced folder locks build files mid-build on Windows, so the
    project is mirrored to a plain folder first (set POCKET_BUILD_DIR to choose it)."""
    if os.name != "nt" or "onedrive" not in str(MOBILE).lower():
        return MOBILE
    target = Path(os.environ.get("POCKET_BUILD_DIR") or Path.home() / "dev" / "pocket-mobile-build")
    print(f"mirroring {MOBILE} -> {target}", flush=True)
    code = subprocess.run(["robocopy", str(MOBILE), str(target), "/MIR", "/XD", "build", ".dart_tool", ".gradle", ".idea",
                           "/XF", "local.properties", "*.iml", "/NFL", "/NDL", "/NJH", "/NJS", "/NP"]).returncode
    if code >= 8:  # robocopy: 0-7 are success codes
        sys.exit(f"robocopy failed with code {code}")
    return target


def apk() -> None:
    """Release APK. API_BASE / AGENT_BASE must be addresses a phone can reach (never localhost).
    Set POCKET_CLEARTEXT=true only for a test build that talks plain HTTP to a laptop on Wi-Fi."""
    where = _android_build_dir()
    run([flutter(), "pub", "get"], where)
    run([flutter(), "build", "apk", "--release", *dart_defines()], where)
    built = where / "build" / "app" / "outputs" / "flutter-apk" / "app-release.apk"
    out = ROOT / ".local" / "pocket.apk"
    out.parent.mkdir(exist_ok=True)
    shutil.copyfile(built, out)
    print(f"APK: {out}  ({out.stat().st_size / 1_000_000:.1f} MB)")


def serve_web() -> None:
    run([sys.executable, "-m", "http.server", "5173", "--bind", "127.0.0.1", "--directory", str(MOBILE / "build" / "web")])


def eval_target(name: str) -> None:
    run(["uv", "run", "python", f"evals/{name}.py", *sys.argv[2:]])


TARGETS = {
    "setup": setup, "dev": dev, "migrate": migrate, "seed-demo": seed_demo, "funds": funds, "sms-variants": sms_variants,
    "lint": lint, "typecheck": typecheck, "test": test, "l10n": l10n, "app": app, "web": web, "apk": apk, "serve-web": serve_web,
    "eval-parsers": lambda: eval_target("eval_parsers"), "eval-insights": lambda: eval_target("eval_insights"),
    "eval-composer": lambda: eval_target("eval_composer"), "eval-chats": lambda: eval_target("eval_chats"),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in TARGETS:
        sys.exit("targets: " + " ".join(TARGETS))
    TARGETS[sys.argv[1]]()
