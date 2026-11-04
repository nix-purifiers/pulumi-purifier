{
  lib,
  runCommand,
  python3,
  fetchurl,
  fetchgit,
  writeText,
  sdkVersion,
  purifier,
  core,
  gnutar,
  gzip,
  stdenv,
  ...
}@scope:
{
  src,
  lockFile ? src + "/pulumi-purifier.lock.json",
  fetchers ? { },
  doCheck ? false,
  checkCommand ? "",
}:
let
  lock = purifier.checkLock (
    import ./read-lock.nix { inherit lib; } {
      inherit src lockFile;
      system = stdenv.hostPlatform.system;
    }
  );
  prepared = import ./environment.nix scope { inherit lock fetchers; };
  source = lib.cleanSourceWith {
    inherit src;
    filter =
      path: type:
      !(builtins.elem (baseNameOf path) [
        ".git"
        ".pulumi-purifier"
        ".consumer-pulumi"
        ".pulumi"
        "result"
        "__pycache__"
      ]);
  };
  driver = lib.fileset.toSource {
    root = ../.;
    fileset = lib.fileset.unions [
      ../pulumi_purifier/common.py
      ../pulumi_purifier/layout.py
      ../native/check.py
    ];
  };
  companion = writeText "pulumi-purifier.lock.json" (builtins.readFile lockFile);
  project = runCommand "pulumi-native-project" { } ''
    export HOME="$TMPDIR/home" PULUMI_HOME="$TMPDIR/home" PULUMI_SKIP_UPDATE_CHECK=true
    mkdir -p "$HOME"
    cp -r ${source} source
    chmod -R u+w source
    cp ${companion} source/pulumi-purifier.lock.json
    ${python3}/bin/python3 ${driver}/native/check.py "$PWD/source" "$TMPDIR/private" ${prepared.output} ${core}/bin/pulumi
    export PULUMI_PURIFIER_PLUGIN_DIR="$TMPDIR/private/plugins" PULUMI_PURIFIER_FROZEN=1
    export PULUMI_IGNORE_AMBIENT_PLUGINS=true PULUMI_DISABLE_AUTOMATIC_PLUGIN_ACQUISITION=true
    pulumi=${core}/bin/pulumi
    cd source
    ${lib.optionalString doCheck checkCommand}
    mkdir -p "$out/.pulumi-purifier/plugins"
    cp -r . "$out/"
    cp -r ${prepared.packages}/. "$out/.pulumi-purifier/plugins/"
  '';
  release =
    runCommand "pulumi-native-release"
      {
        nativeBuildInputs = [
          gnutar
          gzip
        ];
      }
      ''
        mkdir -p "$out"
        tar --sort=name --mtime=@1 --owner=0 --group=0 --numeric-owner -czf "$out/project.tar.gz" -C ${project} .
      '';
in
{
  packages = {
    default = project;
    inherit project;
    environment = prepared.output;
  };
  tests = project;
  inherit release;
  fetches = lock.entries;
}
