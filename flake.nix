{
  description = "Pants build system flake for pants-utils";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        # Shared packages for both FHS and shell
        commonPackages = with pkgs; [
          # Python interpreters
          python310
          python311
          python312
          python312Packages.pip
          python312Packages.setuptools
          python312Packages.certifi
          python312Packages.virtualenv
          # Required tools
          bash
          curl
          git
          git-lfs
          cacert
          unzip
          # Development tools
          black
          mypy
          # Secrets
          infisical
        ];

        # System libraries needed for FHS
        systemLibraries = with pkgs; [
          stdenv.cc.cc.lib
          zlib
          fuse3
          icu
          nss
          openssl
          expat
        ];

        # Inner pants runner script
        pantsRunner = pkgs.writeScript "pants-runner.sh" ''
          #!/usr/bin/env bash
          export PATH="${pkgs.unzip}/bin:$HOME/.local/bin:$PATH"
          export SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
          export REQUESTS_CA_BUNDLE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt
          exec pants "$@"
        '';

        # FHS environment for running Pants
        pantsFHS = pkgs.buildFHSEnv {
          name = "pants-fhs";
          targetPkgs = _: commonPackages ++ systemLibraries;
          runScript = "${pantsRunner}";
        };

        # Pants wrapper that downloads and runs pants in FHS
        pantsWrapped = pkgs.writeShellScriptBin "pants" ''
          PANTS_LAUNCHER="$HOME/.local/bin/pants"

          # Download and install pants launcher if not present
          if [ ! -f "$PANTS_LAUNCHER" ]; then
            echo "Downloading Pants launcher..." >&2
            ${pkgs.curl}/bin/curl -L https://static.pantsbuild.org/setup/get-pants.sh | ${pkgs.bash}/bin/bash
          fi

          # Run pants in FHS environment
          exec ${pantsFHS}/bin/pants-fhs "$@"
        '';
      in {
        devShells.default = pkgs.mkShell {
          buildInputs = [ pantsWrapped ] ++ commonPackages;

          shellHook = ''
            # Setup aliases
            alias ipants='infisical run --path=/infra -- pants'
            alias apants='infisical run --path=/apps -- pants'
          '';
        };
      });
}
