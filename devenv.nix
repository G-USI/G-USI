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
  data = (import ./nix/pants/versions.nix).${version};
  arch = data.${system} or null;
  # Interpreter era mapping - keep in sync with mkPants in flake.nix.
  interpreter =
    if data.python == "python39" then pkgs.python39
    else if data.python == "python311" then pkgs.python311
    else if data.python == "python314" then pkgs.python314
    else throw "devenv: unsupported interpreter era ${data.python} for pants ${version}";
  pants =
    if arch == null then null
    else pkgs.callPackage ./nix/pants {
      inherit interpreter;
      pantsVersion = version;
      pantsUrl = arch.url;
      pantsHash = arch.hash;
      deps = arch.deps;
    };
in
{
  packages =
    [ pkgs.git ]
    ++ lib.optionals (pants != null) [ pants ];

  enterShell = lib.optionalString (pants == null) ''
    echo "devenv: pants ${version} has no ${system} packaging (upstream wheel gap) - Pants goals are unavailable in this shell"
  '';
}
