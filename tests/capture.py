import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="pulumi-cold-") as temporary:
    root = Path(temporary) / "project"
    shutil.copytree(repo / "examples/minimal", root)
    lock = root / "pulumi-purifier.lock.json"
    lock.unlink()
    ambient = Path(temporary) / "home"
    ambient.mkdir()
    (ambient / "preserve").write_text("ambient state")
    env = dict(
        os.environ,
        PULUMI_HOME=str(ambient),
        XDG_CACHE_HOME=str(Path(temporary) / "cache"),
        PULUMI_SKIP_UPDATE_CHECK="true",
    )

    def capture(*args, success=True):
        result = subprocess.run(
            [sdk / "bin/pulumi-purifier", "lock", "--project", root, *args],
            env=env,
            text=True,
            capture_output=True,
            timeout=1200,
        )
        assert (result.returncode == 0) == success, result

    capture()
    data = json.loads(lock.read_text())
    assert set(data["systems"]) == {"x86_64-linux", "aarch64-linux"}
    for selected in data["systems"].values():
        assert {entry["pulumi"]["spec"]["Name"] for entry in selected["entries"]} == {
            "yaml",
            "random",
        }
        assert all(
            entry["url"].startswith("https://") and entry["hash"].startswith("sha256-")
            for entry in selected["entries"]
        )
    before = lock.read_bytes()
    capture()
    assert lock.read_bytes() == before
    source = root / "Pulumi.yaml"
    source.write_text("not: [valid YAML")
    capture("--update", success=False)
    assert lock.read_bytes() == before
    assert list(ambient.iterdir()) == [ambient / "preserve"]
print(
    "Cold native Pulumi capture, both host closures, stable verification, atomic failure and isolated state passed"
)
