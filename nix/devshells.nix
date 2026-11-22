# Plugins dev shell. Pants is resolved by the flake from this repo's
# pants.toml and passed in as a derivation. The aarch64 branch ignores
# `pants` as a derivation: plugin dev is CI-verified on x86_64 only,
# and whether the pinned release is packaged for aarch64 is
# era-dependent, so it explains instead of failing. Reading
# `pants.version` stays lazy - it never forces an unbuildable
# derivation.
{
  system,
  nixpkgs,
  pants,
}:
{
  default =
    if system == "x86_64-linux" then
      nixpkgs.legacyPackages.${system}.mkShell {
        packages = [
          pants
          nixpkgs.legacyPackages.${system}.git
        ];
      }
    else
      nixpkgs.legacyPackages.${system}.mkShell {
        shellHook = ''
          echo "pants ${pants.version}: plugins dev is x86_64-only (CI-verified); aarch64 packaging is era-dependent - see nix/pants/versions (2.33+ packaged)"
        '';
      };
}
