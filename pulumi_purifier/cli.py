import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from .capture import capture
from .common import original_environment, run
from .runtime import execute, realize


def locate(project=None, lock=None, flags=()):
    selected = project or os.environ.get("PULUMI_PURIFIER_PROJECT")
    for index, value in enumerate(flags):
        if value in ("-C", "--cwd") and index + 1 < len(flags):
            selected = flags[index + 1]
        elif value.startswith("--cwd="):
            selected = value.split("=", 1)[1]
    root = Path(selected or Path.cwd()).expanduser().resolve()
    if not selected:
        for candidate in (root, *root.parents):
            if (candidate / "Pulumi.yaml").exists() or (
                candidate / "Pulumi.yml"
            ).exists():
                root = candidate
                break
    companion = Path(
        lock
        or os.environ.get("PULUMI_PURIFIER_LOCK", root / "pulumi-purifier.lock.json")
    ).resolve()
    return root, companion


def main_impl():
    args = sys.argv[1:]
    if args[:1] == ["--native"]:
        flags = args[1:]
        root, companion = locate(flags=flags)
        if not companion.exists():
            print(
                "pulumi-purifier: no lockfile; using ordinary impure Pulumi plugin resolution",
                file=sys.stderr,
            )
            return subprocess.call(
                [os.environ["PULUMI_PURIFIER_ORIGINAL"], *flags],
                env=original_environment(),
            )
        if any(flag in ("--help", "-h") for flag in flags) or flags[:1] == ["version"]:
            return subprocess.call(
                [os.environ["PULUMI_PURIFIER_ORIGINAL"], *flags],
                env=original_environment(),
            )
        return execute(root, companion, flags)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["lock", "prefetch", "exec", "bundle", "publish"]
    )
    parser.add_argument("--project", type=Path)
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--tag", default="v0.1.0")
    opts, rest = parser.parse_known_args(args)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    root, companion = locate(opts.project, opts.lock)
    if opts.action == "lock":
        capture(root, companion, opts.update)
    elif opts.action == "prefetch":
        realize(root, companion)
    elif opts.action == "exec":
        if not rest:
            raise ValueError("Pass a command after --")
        if Path(rest[0]).name == "pulumi":
            root, companion = locate(opts.project, opts.lock, rest[1:])
            return execute(root, companion, rest[1:])
        realize(root, companion)
        env = original_environment()
        env.update(
            PULUMI_PURIFIER_PROJECT=str(root), PULUMI_PURIFIER_LOCK=str(companion)
        )
        env["PATH"] = (
            os.environ["PULUMI_PURIFIER_SDK"] + "/bin" + os.pathsep + env["PATH"]
        )
        return subprocess.call(rest, cwd=root, env=env)
    else:
        realize(root, companion)
        expression = (
            "import "
            + json.dumps(
                os.environ["PULUMI_PURIFIER_SDK"]
                + "/lib/pulumi-purifier/nix/release.nix"
            )
            + " {root="
            + json.dumps(str(root))
            + ";lockFile="
            + json.dumps(str(companion))
            + ";}"
        )
        output = Path(
            run(
                [
                    "nix",
                    "build",
                    "--impure",
                    "--no-link",
                    "--print-out-paths",
                    "--expr",
                    expression,
                ]
            ).strip()
        )
        archive = output / "project.tar.gz"
        if opts.action == "bundle":
            print(archive)
        else:
            subprocess.run(
                [
                    os.environ["PULUMI_PURIFIER_GH"],
                    "release",
                    "upload",
                    opts.tag,
                    str(archive),
                    "--clobber",
                ],
                cwd=root,
                check=True,
            )
    return 0


def main():
    try:
        raise SystemExit(main_impl())
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print("pulumi-purifier: " + str(error), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
