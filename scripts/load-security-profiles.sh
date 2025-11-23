#!/usr/bin/env bash
# Script to load security profiles (AppArmor, SELinux, seccomp)
# For P07 Container Hardening (C2 ★★2)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Loading Security Profiles ==="
echo ""

# Check if running with sufficient privileges
if [ "$EUID" -ne 0 ] && ! command -v sudo &> /dev/null; then
    echo "⚠️  Warning: Not running as root and sudo not available"
    echo "   Some profiles may not load"
fi

# 1. Load AppArmor profile (Linux only)
if command -v apparmor_parser &> /dev/null; then
    echo "📋 Loading AppArmor profile..."
    if [ -f "$PROJECT_ROOT/apparmor-profile" ]; then
        if [ "$EUID" -eq 0 ]; then
            apparmor_parser -r "$PROJECT_ROOT/apparmor-profile"
        else
            sudo apparmor_parser -r "$PROJECT_ROOT/apparmor-profile"
        fi
        echo "✅ AppArmor profile 'secdev-app' loaded"
    else
        echo "❌ AppArmor profile not found"
    fi
else
    echo "⏭️  AppArmor not available (skip on macOS/Windows)"
fi

echo ""

# 2. Verify seccomp profile exists
if [ -f "$PROJECT_ROOT/seccomp-profile.json" ]; then
    echo "✅ Seccomp profile available: seccomp-profile.json"
else
    echo "❌ Seccomp profile not found"
    exit 1
fi

echo ""
echo "=== Profile Loading Complete ==="
echo ""
echo "To use profiles with Docker Compose:"
echo "  1. Uncomment security_opt lines in docker-compose.yml"
echo "  2. Run: docker compose up"
echo ""
echo "To verify AppArmor profile:"
echo "  sudo aa-status | grep secdev-app"
