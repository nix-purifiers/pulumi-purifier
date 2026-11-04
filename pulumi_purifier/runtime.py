import hashlib
import json
import os
from pathlib import Path
import subprocess

from .common import canonical, load, original_environment, run
from .layout import configure


def realize(root, companion):
    data = load(companion)
    sdk = os.environ["PULUMI_PURIFIER_SDK"]
    home = Path(
        original_environment().get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
    )
    key = hashlib.sha256(str(root).encode()).hexdigest()[:20]
    generation = hashlib.sha256(companion.read_bytes() + sdk.encode()).hexdigest()[:20]
    state = home / "pulumi-purifier" / key / generation
    state.mkdir(parents=True, exist_ok=True)
    profile = state / "environment-profile"
    if not profile.exists():
        expression = (
            "import "
            + json.dumps(sdk + "/lib/pulumi-purifier/nix/realize.nix")
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";sdk="
            + json.dumps(sdk)
            + ";}"
        )
        run(
            [
                "nix",
                "build",
                "--impure",
                "--expr",
                expression,
                "--out-link",
                str(profile),
            ]
        )
    manifest = json.loads(Path(json.loads(profile.read_text())["output"]).read_text())
    if manifest["sdk"] != data["sdk"]:
        raise ValueError("Prepared Pulumi SDK differs from the lock")
    return state, data, manifest


def execute(root, companion, args, environment=None, verify_only=False):
    state, data, manifest = realize(root, companion)
    env = configure(state / "session", manifest["packages"], environment)
    binary = os.environ["PULUMI_PURIFIER_CORE"]
    selected = canonical(
        json.loads(run([binary, "plugin", "purifier-specs"], cwd=root, env=env))
    )
    if selected != canonical(manifest["selection"]):
        raise ValueError(
            "Pulumi plugin selection changed; run pulumi-purifier lock --update"
        )
    if verify_only:
        return 0
    env.update(PULUMI_PURIFIER_PROJECT=str(root), PULUMI_PURIFIER_LOCK=str(companion))
    normalized = list(args)
    for index, argument in enumerate(normalized):
        if argument in ("-C", "--cwd") and index + 1 < len(normalized):
            normalized[index + 1] = str(root)
        elif argument.startswith("--cwd="):
            normalized[index] = "--cwd=" + str(root)
    return subprocess.call([binary, *normalized], cwd=root, env=env)
