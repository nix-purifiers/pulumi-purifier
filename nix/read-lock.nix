{ lib }:
{
  src,
  lockFile ? src + "/pulumi-purifier.lock.json",
  system ? builtins.currentSystem,
}:
let
  raw = if builtins.pathExists lockFile then builtins.fromJSON (builtins.readFile lockFile) else { };
  data = if builtins.isAttrs raw then raw else { };
  systems = data.systems or { };
  selected = if builtins.isAttrs systems then systems.${system} or { } else { };
  entries = selected.entries or [ ];
  safe =
    s:
    builtins.isString s
    && builtins.match "[A-Za-z0-9_.+-]+" s != null
    && !(builtins.elem s [
      "."
      ".."
    ]);
  spec =
    s:
    builtins.isAttrs s
    && safe (s.Name or null)
    && builtins.elem (s.Kind or null) [
      "language"
      "resource"
      "analyzer"
      "converter"
      "tool"
    ]
    && safe (s.Version or null)
    && builtins.isString (s.PluginDownloadURL or null)
    && ((s.Checksums or null) == null || builtins.isAttrs s.Checksums);
  shape =
    (data.version or null) == 1
    && (data.purifier or null) == "pulumi"
    && builtins.isString (data.sdk or null)
    && builtins.isList (data.selection or null)
    && builtins.all spec data.selection
    && builtins.isAttrs selected
    && builtins.isList entries
    && builtins.all (
      e:
      builtins.isAttrs e
      && safe (e.path or null)
      && builtins.isString (e.url or null)
      && lib.hasPrefix "https://" e.url
      && builtins.isString (e.hash or null)
      && builtins.match "sha256-[A-Za-z0-9+/]{43}=" e.hash != null
      && builtins.isList (e.mirrors or null)
      && builtins.all builtins.isString e.mirrors
      && builtins.isAttrs (e.pulumi or null)
      && safe (e.pulumi.directory or null)
      && spec (e.pulumi.spec or null)
      &&
        e.pulumi.directory == e.pulumi.spec.Kind + "-" + e.pulumi.spec.Name + "-v" + e.pulumi.spec.Version
    ) entries;
  valid =
    shape
    && builtins.hasAttr system systems
    && builtins.length entries == builtins.length data.selection
    && builtins.length (lib.unique (map (e: e.path) entries)) == builtins.length entries
    && builtins.length (lib.unique (map (e: e.pulumi.directory) entries)) == builtins.length entries
    &&
      lib.sort builtins.lessThan (map (e: builtins.toJSON e.pulumi.spec) entries)
      == lib.sort builtins.lessThan (map builtins.toJSON data.selection);
in
{
  purifier = "pulumi";
  inherit data selected entries;
  problems =
    lib.optional (!valid)
      "Pulumi lock is missing, malformed, or has no closure for this system; run pulumi-purifier lock --update";
  outputs = {
    packages = [
      "default"
      "environment"
      "project"
    ];
    tests = [ "default" ];
    release = [ "default" ];
  };
}
