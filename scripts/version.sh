#!/usr/bin/env bash
# Bump the integration version, commit, and tag — like `npm version`.
#
#   scripts/version.sh patch          0.1.0 -> 0.1.1
#   scripts/version.sh minor          0.1.1 -> 0.2.0
#   scripts/version.sh major          0.2.0 -> 1.0.0
#   scripts/version.sh 1.2.3          set an explicit version
#
# Commits as "v<version>" and creates tag "v<version>". Does not push;
# `git push --follow-tags` afterwards triggers the release workflow.
set -euo pipefail

cd "$(dirname "$0")/.."
MANIFEST="custom_components/vornado_transom/manifest.json"

BUMP="${1:-}"
if [[ -z "$BUMP" ]]; then
  echo "usage: $0 major|minor|patch|<x.y.z>" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "error: working tree not clean; commit or stash first" >&2
  exit 1
fi

CURRENT="$(python3 -c "import json; print(json.load(open('$MANIFEST'))['version'])")"

case "$BUMP" in
  major|minor|patch)
    IFS=. read -r MAJ MIN PAT <<< "$CURRENT"
    case "$BUMP" in
      major) NEW="$((MAJ + 1)).0.0" ;;
      minor) NEW="$MAJ.$((MIN + 1)).0" ;;
      patch) NEW="$MAJ.$MIN.$((PAT + 1))" ;;
    esac
    ;;
  *)
    if [[ ! "$BUMP" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      echo "error: '$BUMP' is not major/minor/patch or a valid x.y.z version" >&2
      exit 1
    fi
    NEW="$BUMP"
    ;;
esac

if git rev-parse -q --verify "refs/tags/v$NEW" >/dev/null; then
  echo "error: tag v$NEW already exists" >&2
  exit 1
fi

python3 - "$MANIFEST" "$NEW" <<'EOF'
import re, sys
path, new = sys.argv[1], sys.argv[2]
with open(path) as f:
    text = f.read()
text, count = re.subn(
    r'("version":\s*")[^"]+(")', rf"\g<1>{new}\g<2>", text, count=1
)
assert count == 1, "version key not found in manifest"
with open(path, "w") as f:
    f.write(text)
EOF

git add "$MANIFEST"
git commit -m "v$NEW"
git tag "v$NEW"

echo "v$NEW"
echo "now run: git push --follow-tags"
