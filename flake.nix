{
  description = "Type Change Tracking Bot";

  inputs = {
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { nixpkgs, pyproject-nix, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
    let
      project = pyproject-nix.lib.project.loadPyproject {
        projectRoot = ./.;
      };

      pkgs = nixpkgs.legacyPackages.${system};

      python = pkgs.python3;

    in
    {
      # Create a development shell containing dependencies from `pyproject.toml`
      devShells.default =
        let
          arg = project.renderers.withPackages { inherit python; };
          pythonEnv = python.withPackages arg;

        in
        pkgs.mkShell { packages = [ pythonEnv ]; };

      # Build our package using `buildPythonPackage
      packages.default =
        let
          attrs = project.renderers.buildPythonPackage { inherit python; };
        in
        python.pkgs.buildPythonPackage (attrs);
    });
}
