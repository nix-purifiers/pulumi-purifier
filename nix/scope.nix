{
  pkgs,
  nixpkgsSrc,
  purifierSrc,
}:
pkgs.lib.makeScope pkgs.newScope (scope: {
  original = pkgs.pulumi;
  core = scope.original.overrideAttrs (old: {
    postPatch = (old.postPatch or "") + "\n${pkgs.python3}/bin/python3 ${../native/patch-cli.py}\n";
    postConfigure =
      (old.postConfigure or "")
      + "\nchmod -R u+w vendor/github.com/pulumi/pulumi/sdk/v3\n${pkgs.python3}/bin/python3 ${../native/patch-sdk.py} ${../native/capture.go}\n";
  });
  purifier = import (purifierSrc + "/nix/lib") { inherit (pkgs) lib; };
  sdkVersion = builtins.hashString "sha256" (
    builtins.toJSON {
      nixpkgs = toString nixpkgsSrc;
      pulumi = toString scope.original.src;
      patch = builtins.hashFile "sha256" ../native/patch-cli.py;
      sdkPatch = builtins.hashFile "sha256" ../native/patch-sdk.py;
      capture = builtins.hashFile "sha256" ../native/capture.go;
    }
  );
  cli = scope.callPackage ./cli.nix { inherit nixpkgsSrc purifierSrc; };
  buildPulumiProject = scope.callPackage ./build-project.nix { };
})
