# g-usi compatibility contract

This document is the contract between g-usi and downstream repositories
(e.g. Neuroslav) that consume it for Pants-on-NixOS and the gusi pants
plugins. It defines how downstream consumes g-usi, what g-usi owns at
runtime, how releases are cut, and what downstream may never do.

Everything here is normative. If reality and this file disagree, that is
a bug - fix one of the two.

## The contract in one paragraph

Downstream's only verbs are:

1. bump the g-usi release pin (a `vX.Y.Z` tag), and
2. pass additive parameters to the documented API surface.

Everything downstream hand-rolls today (compat library sets, cache
sweeps, environment exports, ELF forensics) is being absorbed into the
g-usi API over the WS1-4 series. There are no behavioral flags
downstream can abuse: if a knob is needed, it is a parameter here.

## Consuming g-usi

### Supported present: dual pin, one revision

g-usi is consumed through two pins that MUST resolve to the same
revision - the same `vX.Y.Z` tag:

1. **Flake input** - the nix environment and the Pants package:

   ```nix
   inputs.gusi.url = "git+https://codefloe.com/G-USI/g-usi.git?ref=vX.Y.Z";
   ```

   The input name is the consumer's choice - every snippet in this
   document (and the README) uses `gusi`; adjust `inputs.gusi` /
   `nix flake update gusi` references if you name it differently.

   consumed via the pinned builders
   (`pinned.<system>.mkPantsPinned` / `pinned.<system>.fromPantsToml`)
   or the lib builders (see the README's *Pants from Nix* chapter).

2. **Git submodule** - the plugins, on `pythonpath`:

   ```bash
   git submodule add https://codefloe.com/G-USI/g-usi.git 3rdparty/pants/g-usi
   ```

   ```toml
   [GLOBAL]
   pythonpath = ["%(buildroot)s/3rdparty/pants/g-usi/src/python"]
   pants_ignore.add = ["3rdparty/pants/g-usi"]
   ```

The same-tag rule is the whole point: the flake input and the submodule
are one logical dependency, never two. They bump together or not at
all. Two pins at different revisions is unsupported and the failure
modes (plugins built against a different Pants than the packaged one)
are precisely the opaque ones this contract exists to kill.

### Bump procedure (downstream)

```bash
# 1. flake input -> the new tag, then refresh the lock
$EDITOR flake.nix                 # ref = "vX.Y.Z"
nix flake update gusi             # or: devenv update

# 2. submodule -> the SAME tag
git -C 3rdparty/pants/g-usi fetch --tags origin
git -C 3rdparty/pants/g-usi checkout vX.Y.Z
git add 3rdparty/pants/g-usi && git commit -m "bump g-usi -> vX.Y.Z"
```

### Cross-checking the pins

```bash
# submodule resolves to (must print exactly vX.Y.Z):
git -C 3rdparty/pants/g-usi describe --tags --exact-match

# flake input resolves to (rev must equal the peeled tag commit):
git ls-remote origin refs/tags/vX.Y.Z^{}   # from any g-usi checkout
nix flake metadata gusi                    # .revision, in the consumer
```

### Convergence target (experimental - not yet the contract)

The end state retires the submodule: the plugins ride the flake input's
store path and downstream holds ONE pin.

For nix-generated config:

```nix
pythonpath = [ "${inputs.gusi}/src/python" ]
```

For a static `pants.toml`, via Pants env interpolation (the consumer's
devenv exports `GUSI_SRC = "${inputs.gusi}"`):

```toml
[GLOBAL]
pythonpath = ["%(env.GUSI_SRC)s/src/python"]
```

This mode is **experimental** until Neuroslav proves it end to end
(Pants has not historically been exercised with `pythonpath` entries
outside the buildroot). Until then, dual-pin-same-tag is the contract;
migrating to single-pin is a downstream one-liner per the above when it
is promoted.

### FHS retirement

The pre-monorepo flake (anything at or before `31bb99f`: the
`buildFHSUserEnv` + downloaded-launcher era) is **dead**. It is
reachable through history on purpose - the fix is pin-bumping, not
history rewriting. Consumers on it must jump to at least the first
release tag (`v0.1.0`). There is no upgrade path from the FHS surface;
the patchelf-native surface is a replacement, not a successor, of it.

## Releases and versioning

- Releases are **annotated tags** `vX.Y.Z`, cut from `dev` only.
- Tags are prepared by `scripts/release.sh` (below) and **pushed by the
  human** - the script never pushes; it prints the exact command.
- `v0.1.0` is the baseline: the first dev commit carrying this contract.
  Everything before it is history, not a release.

Version semantics (semver with the usual 0.x caveat - during `0.x`, a
minor bump may break; `1.0` declares the contract stable):

- **X (major)** - breaking: a removal from the API surface, the
  `LD_LIBRARY_PATH` transitional export being dropped, a consumption
  mode being retired, a nixpkgs floor raise that breaks existing
  consumers.
- **Y (minor)** - additive: new parameters (`extraLibs`, `extraEnv`),
  new builders (`mkPantsEnvironment`), new tools (`gusi-probe`), newly
  packaged Pants releases (additive: consumers opt in by version).
- **Z (patch)** - fixes: sweep fixes, version-data corrections, docs.

Every release should record in its tag message (or an attached forge
release): the nixpkgs revision and glibc it builds against, the
packaged Pants release range, and any parameter-surface change.

### scripts/release.sh

```console
$ scripts/release.sh v0.2.0            # prepare + create the tag
$ scripts/release.sh v0.2.0 --dry-run  # everything except tag creation
```

The script enforces: `vX.Y.Z` format, tag does not already exist
(locally or on origin), working tree clean, `HEAD` is exactly
`origin/dev`, and `nix flake check` green - then creates the annotated
tag and prints the push command for the human. Dry-run relaxes the
HEAD==origin/dev requirement to a warning (it is for rehearsing from
feature branches) but runs every other check, including `nix flake
check`.

After pushing the tag on codefloe, the human syncs the mirrors
(codeberg, github) so flake-input URLs against any of them resolve the
same tag.

## Additive parameter surface

Present surface (stable, additive-only evolution):

```nix
mkPants {
  version       # explicit Pants version, or
, pantsToml     # path to the consumer's pants.toml (via fromPantsToml)
, extraPythons  # [ pkgs.python314 ... ] exposed on the wrapper's PATH
, deps          # (internal, generated)
}
```

Forward-declared (landing in upcoming releases; names are final,
availability is not yet):

```nix
mkPantsEnvironment {
  pantsVersion ? null   # one of pantsVersion / pantsToml
, pantsToml   ? null
, extraPythons ? [ ]
, extraLibs    ? [ ]    # appended to the compat library set
, extraEnv     ? { }    # attrset merged over the default env
}
```

The additive-only guarantee: existing call sites that do not use a new
parameter evaluate to byte-identical derivations after it lands. New
parameters get safe defaults; nothing is ever removed inside a major.

## Runtime ownership boundary

**g-usi owns** every ELF that lives under the swept cache roots:

- roots: `<cache>/pants/named_caches` and the scie interpreter cache
  `<xdg-or-home>/.cache/nce`, resolved through exactly the chain Pants
  itself uses - `PANTS_HOME` > `$XDG_CACHE_HOME/pants` >
  `$HOME/.cache/pants` > passwd home > (nothing resolvable: exit 0);
- mechanism: the `pants-patch-caches` sweep (interpreter rewrite +
  rpath append for executables; ldd-gated rpath add for shared
  objects), stamp-keyed to the wrapper's interpreter+rpath so any
  g-usi bump that changes either forces exactly one re-sweep.

**Downstream owns** PATH provisioning for tools exec'd mid-run from
Pants' process sandbox (downloaded-tool plugins: nodejs, terraform,
helm, rustup-init, ...). The sweep cannot rescue these - the exec
happens before any sweep could run. The supported pattern (set the
subsystem version outside `known_versions`, provide the binary via the
invoking shell's PATH) is documented in the README's *Runtime
behavior*; it stays downstream and is not on g-usi's roadmap to absorb.

**Transitional**: the environment API exports an `LD_LIBRARY_PATH`
compat assist so Pants-venv interpreters find `libpython3.x.so` and
friends. It remains until `gusi-probe` proves cached-ELF rpath coverage
on real consumer venvs; its removal ships as a release-note line in a
major bump (an additive param covers stragglers), never as a downstream
edit.

## Support policy

- **Platforms**: x86_64-linux (CI-verified) and aarch64-linux
  (packaged; CI coverage deferred until a arm64 runner label exists -
  releases before then are x86_64-verified only). No macOS.
- **Pants releases**: every stable release from 2.21.0 on is packaged;
  new releases land as minor bumps. Interpreter eras: 2.21-2.24 ->
  python3.9 (via the `nixpkgs-py39` input), 2.25-2.31 -> python3.11,
  2.32+ -> python3.14. On aarch64, 2.27.0-2.32.1 are not packaged
  (upstream `hdrhistogram` ships no arm64 wheels).
- **nixpkgs**: the pinned builders build against this flake's
  nixpkgs-unstable pin - identical store paths for every consumer.
  Downstream may bump its own nixpkgs freely; the nightly CI lane
  (bump -> cold export -> probe) certifies that claim continuously.
- **Binary cache**: none in v1 - a first build is a full build. If
  this hurts, a shared cache is an additive infra change, not a
  contract change.

## Downstream never patches g-usi

No vendored edits, no hand-rolled re-stamping of g-usi-provided
machinery, no local shims around the documented surface. If downstream
needs something the contract does not provide, that is a g-usi bug or
a g-usi feature request: open an issue or PR **here**. Every shim that
exists downstream is a place this contract is wrong - the escalation
path is fixing it at the source.
