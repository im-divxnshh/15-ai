#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir/frontend"
test -f .next/standalone/server.js || { echo 'Run npm run build in frontend first.' >&2; exit 1; }
mkdir -p .next/standalone/.next
cp -R .next/static .next/standalone/.next/
cp -R public .next/standalone/
exec node .next/standalone/server.js
