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
            # Toolchain for analyzing captured Liquid Glass samples. Native
            # captures run directly on the authorized Retina M1 with Apple
            # Command Line Tools; this shell is used only for post-capture
            # analysis and tests.
            packages = with pkgs; [
              actionlint
              (python314.withPackages (
                ps: with ps; [
                  glcontext
                  moderngl
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
              llvmPackages_latest.llvm # disassemble captured Apple arm64 code windows
              ruff
            ];
          };
        }
      );
    };
}
