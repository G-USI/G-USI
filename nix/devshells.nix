# Plugins dev shell. Pants is resolved by the flake from this repo's
# pants.toml and passed in as a derivation. The aarch64 branch ignores
# `pants`: the pinned 2.29.0 era is not packaged there (hdrhistogram
# ships no aarch64 wheels), so it explains instead of failing.
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
          echo "pants 2.29.0 is not packaged for aarch64 (hdrhistogram) - plugins dev is x86_64-only"
        '';
      };
}
