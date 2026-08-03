# SPDX-FileCopyrightText: Magenta ApS <https://magenta.dk>
# SPDX-License-Identifier: MPL-2.0
{
  description = "Dev shell for os2mo-amqp-trigger-organisation-gatekeeper";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  };

  outputs = {nixpkgs, ...}: let
    forAllSystems = nixpkgs.lib.genAttrs nixpkgs.lib.systems.flakeExposed;
  in {
    # `nix fmt`
    formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.alejandra);

    # `nix develop`
    devShells = forAllSystems (system: let
      pkgs = nixpkgs.legacyPackages.${system};
    in {
      default = pkgs.mkShell {
        packages = [
          pkgs.python311
          pkgs.poetry

          # utilities
          pkgs.reuse
        ];

        shellHook = ''
          poetry env use ${pkgs.python311}/bin/python3.11
          eval $(poetry env activate)
          poetry install --no-root
        '';
      };
    });
  };
}
