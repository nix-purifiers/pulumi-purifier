import json
import os
import subprocess

SYSTEMS = {"x86_64-linux": "amd64", "aarch64-linux": "arm64"}
NATIVE_ENV = (
    "PULUMI_PURIFIER_PLUGIN_DIR",
    "PULUMI_PURIFIER_FROZEN",
    "PULUMI_IGNORE_AMBIENT_PLUGINS",
    "PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION",
    "PULUMI_PURIFIER_CAPTURE",
    "PULUMI_PURIFIER_ARCH",
)


def run(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, **kwargs)
    if result.returncode:
        raise ValueError(result.stderr or result.stdout)
    return result.stdout


def original_environment():
    env = dict(os.environ)
    for name, value in json.loads(
        env.pop("PULUMI_PURIFIER_ORIGINAL_ENV", "{}")
    ).items():
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    return env


def load(companion):
    data = json.loads(companion.read_text())
    if data.get("sdk") != os.environ["PULUMI_PURIFIER_SDK_VERSION"]:
        raise ValueError("Pulumi SDK changed; run pulumi-purifier lock --update")
    if os.environ["PULUMI_PURIFIER_SYSTEM"] not in data.get("systems", {}):
        raise ValueError("The Pulumi lock has no closure for this system")
    return data


def canonical(specs):
    return sorted(specs, key=lambda item: json.dumps(item, sort_keys=True))
