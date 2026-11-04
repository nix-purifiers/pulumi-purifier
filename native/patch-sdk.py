from pathlib import Path
import shutil
import sys

base = Path("vendor/github.com/pulumi/pulumi/sdk/v3/go/common/workspace")
p = base / "plugins.go"
s = p.read_text()
s = s.replace(
    "func (spec PluginDescriptor) Download(ctx context.Context) (io.ReadCloser, int64, error) {",
    'func (spec PluginDescriptor) Download(ctx context.Context) (io.ReadCloser, int64, error) {\n if os.Getenv("PULUMI_PURIFIER_FROZEN") == "1" { return nil, -1, fmt.Errorf("plugins are Nix-resolved; use pulumi-purifier lock --update") }',
)
s = s.replace(
    "return source.Download(ctx, *spec.Version, opSy, arch, getHTTPResponse)",
    'if os.Getenv("PULUMI_PURIFIER_CAPTURE") != "" && os.Getenv("PULUMI_PURIFIER_ARCH") != "" { arch = os.Getenv("PULUMI_PURIFIER_ARCH") }\n return source.Download(ctx, *spec.Version, opSy, arch, getHTTPResponse)',
)
s = s.replace(
    "return resp.Body, resp.ContentLength, nil",
    "body, captureErr := purifierCaptureHTTP(req.URL.String(), resp.Body)\n return body, resp.ContentLength, captureErr",
    1,
)
s = s.replace(
    "reader, err := os.Open(tarball)",
    "if err := purifierCaptureArchive(pkgPlugin, tarball); err != nil { return nil, err }\n reader, err := os.Open(tarball)",
    1,
)
s = s.replace(
    "func (info *PluginInfo) Delete() error {",
    'func (info *PluginInfo) Delete() error {\n if os.Getenv("PULUMI_PURIFIER_FROZEN") == "1" { return fmt.Errorf("plugins are Nix-resolved; use pulumi-purifier lock --update") }',
)
s = s.replace(
    "func GetPluginDir() (string, error) {",
    'func GetPluginDir() (string, error) {\n if directory := os.Getenv("PULUMI_PURIFIER_PLUGIN_DIR"); directory != "" { return directory, nil }',
)
p.write_text(s)
shutil.copyfile(sys.argv[1], base / "purifier_capture.go")
p = Path("pluginstorage/download.go")
s = p.read_text().replace(
    "defer contract.IgnoreClose(content)",
    'if os.Getenv("PULUMI_PURIFIER_FROZEN") == "1" { return nil, fmt.Errorf("plugins are Nix-resolved; use pulumi-purifier lock --update") }\n defer contract.IgnoreClose(content)',
    1,
)
p.write_text(s)
