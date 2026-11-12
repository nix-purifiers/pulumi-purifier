{
  lib,
  stdenvNoCC,
  makeWrapper,
  python3,
  nix,
  gh,
  git,
  cacert,
  gnutar,
  gzip,
  unzip,
  coreutils,
  stdenv,
  original,
  core,
  sdkVersion,
  nixpkgsSrc,
  purifierSrc,
}:
stdenvNoCC.mkDerivation {
  pname = "pulumi-purifier";
  version = "0.1.0";
  src = ../..;
  nativeBuildInputs = [ makeWrapper ];
  dontBuild = true;
  installPhase = ''
    mkdir -p "$out/bin" "$out/lib/pulumi-purifier"
    cp -r pulumi_purifier nix lib-overlays pkgs native "$out/lib/pulumi-purifier/"
    install -m755 bin/pulumi-purifier "$out/bin/pulumi-purifier"
    for file in realize release; do
      substituteInPlace "$out/lib/pulumi-purifier/nix/$file.nix" --replace-fail '@nixpkgs@' '${nixpkgsSrc}' --replace-fail '@purifier@' '${purifierSrc}'
    done
    wrapProgram "$out/bin/pulumi-purifier" \
      --prefix PATH : ${
        lib.makeBinPath [
          python3
          nix
          gh
          git
          gnutar
          gzip
          unzip
        ]
      } \
      --set-default SSL_CERT_FILE ${cacert}/etc/ssl/certs/ca-bundle.crt \
      --set-default PULUMI_PURIFIER_GH ${gh}/bin/gh \
      --set PULUMI_PURIFIER_ORIGINAL ${original}/bin/pulumi \
      --set PULUMI_PURIFIER_CORE ${core}/bin/pulumi \
      --set PULUMI_PURIFIER_SYSTEM ${stdenv.hostPlatform.system} \
      --set PULUMI_PURIFIER_SDK_VERSION ${sdkVersion} \
      --set PULUMI_PURIFIER_SDK "$out"
    makeWrapper "$out/bin/pulumi-purifier" "$out/bin/pulumi" --add-flags '--native'
  '';
  meta = {
    description = "Pulumi with locked Nix-resolved dependencies";
    homepage = "https://nix-purifiers.github.io/";
    license = lib.licenses.mit;
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    mainProgram = "pulumi-purifier";
  };
}
