import json
from pathlib import Path
from .common import NATIVE_ENV, original_environment


def configure(state, packages, environment=None):
    env = original_environment() if environment is None else dict(environment)
    env["PULUMI_PURIFIER_ORIGINAL_ENV"] = json.dumps(
        {name: env.get(name) for name in NATIVE_ENV}
    )
    aliases = Path(state) / "plugins"
    aliases.mkdir(parents=True, exist_ok=True)
    expected = {item.name: item for item in Path(packages).iterdir() if item.is_dir()}
    if set(item.name for item in aliases.iterdir() if item.is_dir()) - set(expected):
        raise ValueError("Private Pulumi plugin aliases contain an unlocked plugin")
    for name, item in expected.items():
        destination = aliases / name
        if destination.is_symlink():
            raise ValueError("Private plugin directory must be an ordinary directory")
        destination.mkdir(exist_ok=True)
        for child in item.iterdir():
            alias = destination / child.name
            if alias.is_symlink():
                if alias.resolve() != child.resolve():
                    raise ValueError("Private Pulumi plugin alias changed")
            elif alias.exists():
                raise ValueError("Private Pulumi plugin alias was replaced")
            else:
                alias.symlink_to(child, target_is_directory=child.is_dir())
        if {x.name for x in destination.iterdir()} != {x.name for x in item.iterdir()}:
            raise ValueError("Private Pulumi plugin contains unlocked files")
    env.update(
        PULUMI_PURIFIER_PLUGIN_DIR=str(aliases),
        PULUMI_PURIFIER_FROZEN="1",
        PULUMI_IGNORE_AMBIENT_PLUGINS="true",
        PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION="true",
    )
    env.pop("PULUMI_PURIFIER_CAPTURE", None)
    env.pop("PULUMI_PURIFIER_ARCH", None)
    return env
