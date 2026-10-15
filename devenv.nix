# devenv - contributor environment for the gusi pants plugins.
#
# Pants comes from this repo's own packaging (./nix/pants) at the version
# pinned in ./pants.toml - the same derivation the flake's pinned builders
# produce (see devenv.yaml for the nixpkgs-rev alignment that guarantees
# identical store paths). On systems the pinned release does not package
# (e.g. aarch64 for 2.29.0 - hdrhistogram ships no arm64 wheels), the
# shell degrades to a message instead of failing the eval.
{ pkgs, lib, ... }:

let
  system = pkgs.stdenv.hostPlatform.system;
  version = (builtins.fromTOML (builtins.readFile ./pants.toml)).GLOBAL.pants_version;
  # No nixpkgs-py39 input in devenv.yaml: a cp39-era pin surfaces the
  # lib's informative throw instead of a missing-attribute error.
  pantsLib = import ./nix/pants/lib.nix { inherit pkgs; };
  arch = pantsLib.archOrNull { inherit version system; };
  pants = if arch == null then null else pantsLib.mkPants { inherit version; };
in
{
  packages =
    [ pkgs.git ]
    ++ lib.optionals (pants != null) [ pants ];

  enterShell = lib.optionalString (pants == null) ''
    echo "devenv: pants.toml pins pants ${version}, which has no ${system} packaging (upstream wheel gap) - Pants goals are unavailable in this shell"
  '';
}
