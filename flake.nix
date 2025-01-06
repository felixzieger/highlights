{
  description = "Kindle Clippings to YAML converter";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python-env = pkgs.python3.withPackages (ps: with ps; [
          pyyaml
          pillow
          requests
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python-env
          ];

          shellHook = ''
            echo "Python development environment loaded"
            echo "Required packages: pyyaml, pillow, requests"
          '';
        };

        devShells.dev = pkgs.mkShell {
          buildInputs = with pkgs; [
            python-env
            black
            pylint
            python3Packages.pytest
          ];

          shellHook = ''
            echo "Python development environment loaded"
            echo "Available tools:"
            echo " - black: Code formatter"
            echo " - pylint: Linter"
            echo " - pytest: Testing framework"
            echo "Required packages: pyyaml, pillow, requests"
          '';
        };
      });
} 