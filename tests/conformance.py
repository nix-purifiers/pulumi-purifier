import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import threading

repo = Path(__file__).resolve().parent.parent
sdk = Path(
    subprocess.check_output(
        ["nix", "build", str(repo) + "#", "--no-link", "--print-out-paths"], text=True
    ).strip()
)
with tempfile.TemporaryDirectory(prefix="pulumi proof with spaces ") as temporary:
    temp = Path(temporary)
    root = temp / "project"
    shutil.copytree(repo / "examples/minimal", root)
    backend = temp / "backend"
    backend.mkdir()
    ambient = temp / "home/plugins/language-yaml-v1.38.16/pulumi-language-yaml"
    ambient.parent.mkdir(parents=True)
    ambient.write_text("#!/bin/sh\necho poisoned-language >&2\nexit 88\n")
    ambient.chmod(0o755)
    env = dict(
        os.environ,
        PULUMI_PURIFIER_PROJECT=str(root),
        PULUMI_HOME=str(temp / "home"),
        PULUMI_CONFIG_PASSPHRASE="proof",
        PULUMI_SKIP_UPDATE_CHECK="true",
        XDG_CACHE_HOME=str(temp / "cache"),
    )

    def call(name, *args, success=True, extra=None):
        result = subprocess.run(
            [sdk / "bin" / name, *args],
            cwd=root,
            env=dict(env, **(extra or {})),
            text=True,
            capture_output=True,
            timeout=600,
        )
        assert (result.returncode == 0) == success, result
        return result

    call("pulumi", "login", "file://" + str(backend))
    call("pulumi", "stack", "init", "proof")
    companion = root / "pulumi-purifier.lock.json"
    before = companion.read_bytes()
    source = root / "Pulumi.yaml"
    original = source.read_text()
    outputs = []
    for answer in [42, 43, 42]:
        source.write_text(
            original.replace("min: 42", "min: " + str(answer)).replace(
                "max: 42", "max: " + str(answer)
            )
        )
        call("pulumi", "up", "--yes", "--skip-preview", "--non-interactive")
        outputs.append(call("pulumi", "stack", "output", "answer").stdout.strip())
    assert outputs == ["42", "43", "42"], outputs
    assert companion.read_bytes() == before
    assert "poisoned-language" in ambient.read_text()
    source.write_text(original.replace("version: 4.14.0", "version: 4.13.0"))
    result = call("pulumi", "preview", "--non-interactive", success=False)
    assert "selection changed" in result.stderr or "plugin" in result.stderr, result
    source.write_text(original)
    for args in [
        ("plugin", "install", "resource", "random", "4.14.0", "--reinstall"),
        ("plugin", "rm", "resource", "random", "4.14.0", "--yes"),
    ]:
        assert "Nix-resolved" in call("pulumi", *args, success=False).stderr
    (profile,) = list((temp / "cache/pulumi-purifier").glob("*/*/environment-profile"))
    assert str(sdk) in subprocess.check_output(
        ["nix-store", "--query", "--requisites", str(profile.resolve())], text=True
    )
    manifest = json.loads(Path(json.loads(profile.read_text())["output"]).read_text())
    assert not Path(manifest["packages"]).stat().st_mode & 0o222
    marker = profile.parent / "session/preserve"
    marker.write_text("private state")
    call("pulumi", "preview", "--non-interactive")
    assert marker.read_text() == "private state"

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"42")

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        command = (
            "from urllib.request import urlopen;print(urlopen("
            + repr("http://127.0.0.1:" + str(server.server_port) + "/")
            + ").read().decode())"
        )
        assert (
            call(
                "pulumi-purifier", "exec", "--", "python3", "-c", command
            ).stdout.strip()
            == "42"
        )
    finally:
        server.shutdown()
        server.server_close()
    external = temp / "external-lock.json"
    companion.rename(external)
    flags = {"PULUMI_PURIFIER_LOCK": str(external)}
    call("pulumi", "--cwd", str(root), "preview", "--non-interactive", extra=flags)
    private_credentials = root / ".consumer-pulumi/credentials.json"
    private_credentials.parent.mkdir()
    private_credentials.write_text("private consumer credentials")
    archive = Path(call("pulumi-purifier", "bundle", extra=flags).stdout.strip())
    consumer = temp / "consumer"
    consumer.mkdir()
    with tarfile.open(archive) as package:
        package.extractall(consumer, filter="data")
    assert not (consumer / ".consumer-pulumi").exists()
    assert (
        consumer / "pulumi-purifier.lock.json"
    ).read_bytes() == external.read_bytes()
    for item in [consumer, *consumer.rglob("*")]:
        item.chmod(item.stat().st_mode | 0o200)
    consumer_home = temp / "consumer-home"
    consumer_home.mkdir()
    shutil.copytree(consumer / ".pulumi-purifier/plugins", consumer_home / "plugins")
    # The consumer invokes the unmodified CLI, supplied explicitly by the SDK.
    raw = Path(
        call(
            "pulumi-purifier",
            "exec",
            "--",
            "sh",
            "-c",
            'printf "%s" "$PULUMI_PURIFIER_ORIGINAL"',
            extra=flags,
        ).stdout
    )
    consumer_env = dict(
        os.environ,
        PULUMI_HOME=str(consumer_home),
        PULUMI_CONFIG_PASSPHRASE="proof",
        PULUMI_SKIP_UPDATE_CHECK="true",
        PULUMI_IGNORE_AMBIENT_PLUGINS="true",
        PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION="true",
    )
    for name in ["PULUMI_PURIFIER_FROZEN", "PULUMI_PURIFIER_PLUGIN_DIR"]:
        consumer_env.pop(name, None)
    consumer_backend = temp / "consumer-backend"
    consumer_backend.mkdir()
    for args in [
        ("login", "file://" + str(consumer_backend)),
        ("stack", "init", "consumer"),
        ("up", "--yes", "--skip-preview", "--non-interactive"),
    ]:
        subprocess.run(
            [raw, *args],
            cwd=consumer,
            env=consumer_env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    assert (
        subprocess.check_output(
            [raw, "stack", "output", "answer"],
            cwd=consumer,
            env=consumer_env,
            text=True,
        ).strip()
        == "42"
    )
    fake = temp / "fake-gh"
    publication = temp / "publication.json"
    fake.write_text(
        "#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\nPath("
        + repr(str(publication))
        + ").write_text(json.dumps(sys.argv[1:]))\n"
    )
    fake.chmod(0o755)
    call(
        "pulumi-purifier",
        "publish",
        "--tag",
        "v-proof",
        extra=dict(flags, PULUMI_PURIFIER_GH=str(fake)),
    )
    assert json.loads(publication.read_text()) == [
        "release",
        "upload",
        "v-proof",
        str(archive),
        "--clobber",
    ]
    fallback = temp / "fallback"
    fallback.mkdir()
    assert (
        "ordinary impure"
        in call(
            "pulumi", "version", extra={"PULUMI_PURIFIER_PROJECT": str(fallback)}
        ).stderr
    )
    fake.write_text("#!/bin/sh\nprintf native-out\nprintf native-err >&2\nexit 7\n")
    direct = dict(
        os.environ,
        PYTHONPATH=str(sdk / "lib/pulumi-purifier"),
        PULUMI_PURIFIER_ORIGINAL=str(fake),
        PULUMI_PURIFIER_PROJECT=str(fallback),
    )
    result = subprocess.run(
        ["python3", "-m", "pulumi_purifier.cli", "--native"],
        env=direct,
        text=True,
        capture_output=True,
    )
    assert (
        result.returncode == 7
        and result.stdout == "native-out"
        and result.stderr.endswith("native-err")
    ), result
print(
    "Native Pulumi42/43/42, selection guards, isolated plugins, GC closure, source consumer, publication and fallback passed"
)
