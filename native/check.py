import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from pulumi_purifier.common import canonical, run
from pulumi_purifier.layout import configure

root, state, manifest_file, binary = sys.argv[1:]
manifest = json.loads(Path(manifest_file).read_text())
env = configure(state, manifest["packages"])
selected = canonical(
    json.loads(run([binary, "plugin", "purifier-specs"], cwd=root, env=env))
)
if selected != canonical(manifest["selection"]):
    raise ValueError(
        "Pulumi plugin selection changed; run pulumi-purifier lock --update"
    )
