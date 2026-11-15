#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
binary="$repo_dir/build/silorobot-dashboard"
unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"

if [[ ! -x "$binary" ]]; then
  echo "Dashboard binary missing: $binary" >&2
  echo 'Build first: cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j2' >&2
  exit 2
fi
if [[ "$repo_dir" != "$HOME/rpi4-dashboard" ]]; then
  echo "The service expects the checkout at $HOME/rpi4-dashboard (current: $repo_dir)." >&2
  exit 2
fi

mkdir -p "$unit_dir"
install -m 0644 "$repo_dir/systemd/silorobot-dashboard.service" \
  "$unit_dir/silorobot-dashboard.service"
systemctl --user daemon-reload
systemctl --user enable --now silorobot-dashboard.service
systemctl --user --no-pager --full status silorobot-dashboard.service
