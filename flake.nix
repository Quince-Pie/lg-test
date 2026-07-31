{
  description = "Reproducible analysis environment for Liquid Glass captures";

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
      formatter = forAllSystems ({ pkgs }: pkgs.nixfmt);
      devShells = forAllSystems (
        { pkgs }:
        {
          default = pkgs.mkShell {
            # Toolchain for analyzing the captured Liquid Glass samples
            # (the captures themselves are produced on GitHub's macos-26
            # runners by .github/workflows/capture.yml).
            packages = with pkgs; [
              actionlint
              (python314.withPackages (
                ps: with ps; [
                  numpy
                  scipy
                  opencv4
                  scikit-image
                  matplotlib
                  pillow
                ]
              ))
              imagemagick
              gh # download artifacts: gh run download -n liquid-glass-captures-<run id>
              ruff
            ];
          };
        }
      );
    };
}
