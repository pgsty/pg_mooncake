set -eu
if ! grep -Fqs "pid: %p" "$HOME/.psqlrc"; then
    cat >> "$HOME/.psqlrc" <<'EOF'
\set PROMPT1 '%/ (pid: %p) %R%# '
\set PROMPT2 '  '
EOF
fi
git config devcontainers-theme.show-dirty 1
