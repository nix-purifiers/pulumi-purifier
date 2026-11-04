{
  lib,
  runCommand,
  fetchurl,
  fetchgit,
  writeText,
  python3,
  purifier,
  sdkVersion,
  core,
  ...
}:
{
  lock,
  fetchers ? { },
}:
let
  checked = purifier.checkLock lock;
  archives = purifier.tree (
    {
      name = "pulumi-archives";
      inherit
        runCommand
        fetchurl
        fetchgit
        writeText
        python3
        ;
      entries = checked.entries;
    }
    // fetchers
  );
  install =
    entry:
    let
      s = entry.pulumi.spec;
    in
    "${core}/bin/pulumi plugin install ${lib.escapeShellArg s.Kind} ${lib.escapeShellArg s.Name} ${lib.escapeShellArg s.Version} --file ${archives}/${entry.path} --exact";
  packages = runCommand "pulumi-native-plugins" { } (
    ''
      export HOME="$TMPDIR/home" PULUMI_HOME="$TMPDIR/home" PULUMI_DEV=true PULUMI_SKIP_UPDATE_CHECK=true
      mkdir -p "$HOME" "$out"
    ''
    + lib.concatMapStringsSep "\n" install checked.entries
    + "\n"
    + ''
      cp -r "$HOME/plugins/." "$out/"
      rm -f "$out/"*.lastused "$out/"*.lock
      if find "$out" -name PulumiPlugin.yaml -o -name PulumiPlugin.yml | read -r plugin; then
       echo "Source-based Pulumi plugins require a language dependency provider" >&2
       exit 1
      fi
    ''
  );
  output =
    (writeText "pulumi-environment.json" (
      builtins.toJSON {
        inherit packages;
        inherit (lock.data) sdk selection;
      }
    )).overrideAttrs
      (_: {
        passthru = { inherit packages; };
      });
in
assert lib.assertMsg (
  lock.data.sdk == sdkVersion
) "Pulumi SDK changed; run pulumi-purifier lock --update";
{
  inherit output packages;
}
