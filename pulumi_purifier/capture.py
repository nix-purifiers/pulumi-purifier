import base64
import json
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from .common import SYSTEMS, canonical, original_environment, run


def capture(root, companion, update=False):
    if companion.exists() and not update:
        from .runtime import execute

        with tempfile.TemporaryDirectory(prefix="pulumi-verify-") as temporary:
            env = original_environment()
            env["PULUMI_HOME"] = temporary
            if execute(root, companion, [], environment=env, verify_only=True):
                raise ValueError("Locked Pulumi configuration failed verification")
        return
    binary = os.environ["PULUMI_PURIFIER_CORE"]
    with tempfile.TemporaryDirectory(prefix="pulumi-capture-") as temporary:
        state = Path(temporary)
        home = state / "home"
        home.mkdir()
        env = original_environment()
        for name in (
            "PULUMI_PURIFIER_PLUGIN_DIR",
            "PULUMI_PURIFIER_FROZEN",
            "PULUMI_PURIFIER_CAPTURE",
            "PULUMI_PURIFIER_ARCH",
        ):
            env.pop(name, None)
        env.update(
            PULUMI_HOME=str(home),
            PULUMI_SKIP_UPDATE_CHECK="true",
            PULUMI_IGNORE_AMBIENT_PLUGINS="true",
            PULUMI_DEV="true",
        )
        # The native CLI normally bundles YAML; the Nix CLI provides it through the
        # same native plugin installer so its exact binary enters the captured lock.
        run([binary, "plugin", "install", "language", "yaml"], cwd=root, env=env)
        selection = canonical(
            json.loads(run([binary, "plugin", "purifier-specs"], cwd=root, env=env))
        )
        languages = [x["Name"] for x in selection if x["Kind"] == "language"]
        if languages != ["yaml"]:
            raise ValueError("The initial provider supports native YAML projects")
        specs = state / "specs.json"
        specs.write_text(json.dumps(selection))
        systems = {}
        for system, arch in SYSTEMS.items():
            observed = state / system
            observed.mkdir()
            run(
                [binary, "plugin", "purifier-download", str(specs)],
                cwd=root,
                env=dict(
                    env,
                    PULUMI_PURIFIER_CAPTURE=str(observed),
                    PULUMI_PURIFIER_ARCH=arch,
                ),
            )
            entries = []
            for index, line in enumerate(
                (observed / "records.jsonl").read_text().splitlines()
            ):
                item = json.loads(line)
                url = urlsplit(item["url"])
                if (
                    url.scheme != "https"
                    or url.username
                    or url.password
                    or url.query
                    or url.fragment
                ):
                    raise ValueError(
                        "A public stable HTTPS plugin archive URL is required"
                    )
                run(["nix", "store", "add-file", item["archive"]])
                entries.append(
                    dict(
                        path="archive-" + str(index),
                        url=item["url"],
                        mirrors=[],
                        hash="sha256-"
                        + base64.b64encode(bytes.fromhex(item["sha256"])).decode(),
                        pulumi=dict(directory=item["directory"], spec=item["spec"]),
                    )
                )
            systems[system] = dict(entries=entries)
        candidate = state / "pulumi-purifier.lock.json"
        candidate.write_text(
            json.dumps(
                dict(
                    version=1,
                    purifier="pulumi",
                    sdk=os.environ["PULUMI_PURIFIER_SDK_VERSION"],
                    selection=selection,
                    systems=systems,
                ),
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )
        from .runtime import execute

        if execute(root, candidate, [], environment=env, verify_only=True):
            raise ValueError("Nix-replayed Pulumi plugins failed verification")
        companion.parent.mkdir(parents=True, exist_ok=True)
        staged = companion.with_name(companion.name + ".tmp")
        staged.write_bytes(candidate.read_bytes())
        staged.replace(companion)
