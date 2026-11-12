{
  description = "Locked, Nix-resolved Pulumi dependencies";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        pulumi-purifier = import ./nix/scope.nix {
          pkgs = final;
          nixpkgsSrc = nixpkgs;
          purifierSrc = purifier;
        };
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).pulumi-purifier.cli;
        cli = self.packages.${system}.default;
      });
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/pulumi-purifier";
          meta.description = "Lock native Pulumi dependencies";
        };
      });
      lib.pulumi-purifier = import ./lib-overlays/default { lib = nixpkgs.lib; };
      checks = forAll (
        system:
        let
          p = pkgsFor system;
          b = p.pulumi-purifier.buildPulumiProject {
            src = ./examples/minimal;
            doCheck = true;
            checkCommand = ''
              export PULUMI_CONFIG_PASSPHRASE=proof
              mkdir -p "$TMPDIR/backend"
              "$pulumi" login "file://$TMPDIR/backend"
              "$pulumi" stack init proof
              "$pulumi" up --yes --skip-preview --non-interactive
              test "$("$pulumi" stack output answer)" = 42
              rm -f Pulumi.proof.yaml
            '';
          };
        in
        {
          inherit (b.packages) environment project;
          release = b.release;
          cli = self.packages.${system}.default;
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
