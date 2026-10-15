{
  description = "G-USI nix monorepo - pants packaging + plugins";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    # python3.9 was removed from newer nixpkgs after its EOL; the cp39-era
    # Pants releases (2.21-2.24) build against this hydra-cached branch.
    nixpkgs-py39.url = "github:NixOS/nixpkgs/nixos-24.11";
  };

  outputs =
    { self, nixpkgs, nixpkgs-py39 }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      # Shared builder logic (version resolution, arch handling,
      # pants.toml reading) - see nix/pants/lib.nix. Every Pants
      # packaging flow below goes through it.
      pantsLib = { pkgs, pkgs39 ? null }: import ./nix/pants/lib.nix { inherit pkgs pkgs39; };

      # Any instantiation exposes the pkgs-independent helpers
      # (versionData, latestVersion); pkgs39 is irrelevant for these.
      probe = pantsLib { pkgs = nixpkgs.legacyPackages.x86_64-linux; };
    in
    {
      lib = {
        # System-agnostic builders: the target nixpkgs arrive per call,
        # matching the pre-lib signatures.
        mkPants = pkgs: pkgs39: args: (pantsLib { inherit pkgs pkgs39; }).mkPants args;
        inherit (probe) latestVersion versionData;
        # Read a repo's pants.toml and build exactly the pinned version:
        #   g-usi.lib.fromPantsToml pkgs pkgs39 ./pants.toml
        # or pass { file = ./pants.toml; extraPythons = [...]; } to
        # expose extra interpreters on the wrapper's PATH. Changing
        # [GLOBAL].pants_version in the toml re-resolves the package on
        # the next eval; unknown versions fail loudly once their data is
        # regenerated into nix/pants/versions.nix.
        fromPantsToml = pkgs: pkgs39: target:
          (pantsLib { inherit pkgs pkgs39; }).fromPantsToml pkgs pkgs39 target;
      };

      # Empty until the first entry; consumers can rely on the output
      # existing.
      overlays.default = final: prev: { };

      # Pinned per-system builders: they use THIS flake's nixpkgs, so
      # results are identical for every consumer and a shared binary
      # cache actually hits - builds from the consumer's own nixpkgs
      # differ per input revision and can never be cached.
      pinned = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pkgs39 = nixpkgs-py39.legacyPackages.${system};
          builder = pantsLib { inherit pkgs pkgs39; };
        in
        {
          mkPantsPinned = args: builder.mkPants args;
          fromPantsToml = target: builder.fromPantsToml pkgs pkgs39 target;
        }
      );

      packages = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pkgs39 = nixpkgs-py39.legacyPackages.${system};
          builder = pantsLib { inherit pkgs pkgs39; };
          mangle = nixpkgs.lib.replaceStrings [ "." ] [ "_" ];
        in
        # Versions whose dep closure has no wheels for this system are
        # skipped entirely (hdrhistogram ships no aarch64 wheels, which
        # nulls 2.27-2.32.1).
        nixpkgs.lib.filterAttrs (_: p: p != null) (
          nixpkgs.lib.mapAttrs' (
            version: _:
            nixpkgs.lib.nameValuePair "pants-${mangle version}" (
              if builder.archOrNull { inherit version system; } != null
              then builder.mkPants { inherit version; }
              else null
            )
          ) builder.versionData
        )
        // {
          default = self.packages.${system}."pants-${mangle builder.latestVersion}";
        }
      );

      apps = forAllSystems (
        system:
        rec {
          pants = {
            type = "app";
            program = nixpkgs.lib.getExe self.packages.${system}.default;
          };
          default = pants;
        }
      );

      devShells = forAllSystems (
        system:
        # Passing the built derivation (not this flake) into the devshell
        # module keeps the import free of any self-reference cycle.
        import ./nix/devshells.nix {
          inherit system nixpkgs;
          pants = (pantsLib {
            pkgs = nixpkgs.legacyPackages.${system};
            pkgs39 = nixpkgs-py39.legacyPackages.${system};
          }).mkPants {
            version = (builtins.fromTOML (builtins.readFile ./pants.toml)).GLOBAL.pants_version;
          };
        }
      );

      checks = forAllSystems (
        system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          pkgs39 = nixpkgs-py39.legacyPackages.${system};
          builder = pantsLib { inherit pkgs pkgs39; };
          # One smoke per wheel-era: cp39 (oldest), cp311 (2.31.0),
          # cp314 (latest) - each asserts its own --version output.
          # Versions without data for this system are skipped (aarch64
          # nulls for releases whose dep closure never shipped arm64
          # wheels).
          oldest = nixpkgs.lib.head (nixpkgs.lib.naturalSort (nixpkgs.lib.attrNames builder.versionData));
          hasArch = version: builder.archOrNull { inherit version system; } != null;
          mkSmoke = name: version: extraPythons:
            pkgs.runCommand "pants-${name}-smoke"
              {
                nativeBuildInputs = [
                  (builder.mkPants {
                    inherit version extraPythons;
                  })
                ];
                # pantsd's socket bootstrap does not survive the check
                # sandbox; the version goal does not need it. HOME must
                # point somewhere writable - TMPDIR is guaranteed and
                # portable across Nix versions (unlike /build).
                PANTS_PANTSD = "false";
              }
              ''
                export HOME="$TMPDIR"
                mkdir -p project && cd project
                printf '[GLOBAL]\npants_version = "${version}"\n' > pants.toml
                pants --version > version.out
                grep -qx ${version} version.out || {
                  echo "unexpected version:"; cat version.out; exit 1;
                }
                cp version.out $out
              '';
        in
        nixpkgs.lib.filterAttrs (_: check: check != null) {
          version-smoke =
            if hasArch builder.latestVersion then mkSmoke "latest" builder.latestVersion [ pkgs.python314 ] else null;
          py311-smoke = if hasArch "2.31.0" then mkSmoke "py311" "2.31.0" [ ] else null;
          oldest-smoke = if hasArch oldest then mkSmoke "oldest" oldest [ ] else null;
        }
      );
    };
}
