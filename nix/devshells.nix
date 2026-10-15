# Plugins dev shell. Pants is resolved by the flake from this repo's
# pants.toml and passed in as a derivation. The aarch64 branch ignores
# `pants` as a derivation: the pinned release is not packaged there
# (hdrhistogram ships no aarch64 wheels), so it explains instead of
# failing. Reading `pants.version` stays lazy - it never forces the
# unbuildable derivation.
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
          echo "pants ${pants.version} is not packaged for aarch64 (hdrhistogram) - plugins dev is x86_64-only"
        '';
      };
}
