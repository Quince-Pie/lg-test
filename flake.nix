{
  description = "A Nix Dev Env";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  };

  outputs =
    {
      self,
      nixpkgs,
    }:
    let
      forAllSystems =
        f:
        nixpkgs.lib.genAttrs nixpkgs.lib.platforms.unix (
          system:
          f {
            pkgs = import nixpkgs { inherit system; };
          }
        );
    in
    {
      formatter = forAllSystems ({ pkgs }: pkgs.nixfmt-rfc-style);
      devShells = forAllSystems (
        { pkgs }:
        {
          default = pkgs.mkShell {
            # Toolchain for analyzing the captured Liquid Glass samples
            # (the captures themselves are produced on GitHub's macos-26
            # runners by .github/workflows/capture.yml).
            packages = with pkgs; [
              (python3.withPackages (ps: with ps; [
                numpy
                scipy
                opencv4
                scikit-image
                matplotlib
                pillow
              ]))
              imagemagick
              gh # download artifacts: gh run download -n liquid-glass-captures-<run id>
            ];
          };
        }
      );
    };
}
