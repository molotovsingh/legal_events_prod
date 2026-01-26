#!/bin/bash
# Script to create GitHub releases for v0.11.0 and v0.11.1
# Run this after authenticating with: gh auth login

echo "Creating GitHub releases..."
echo "=========================================="

# Create v0.11.0 release
echo "Creating v0.11.0 release..."
gh release create v0.11.0 \
  --title "v0.11.0 - Provider Architecture Simplification" \
  --notes-file release_notes_v0.11.0.md \
  --target main

if [ $? -eq 0 ]; then
    echo "✅ v0.11.0 release created successfully"
else
    echo "❌ Failed to create v0.11.0 release"
    exit 1
fi

# Create v0.11.1 release
echo ""
echo "Creating v0.11.1 release..."
gh release create v0.11.1 \
  --title "v0.11.1 - Type-Safe Job Enqueuing Hotfix" \
  --notes-file release_notes_v0.11.1.md \
  --target main

if [ $? -eq 0 ]; then
    echo "✅ v0.11.1 release created successfully"
else
    echo "❌ Failed to create v0.11.1 release"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Both releases created successfully!"
echo ""
echo "View releases at:"
echo "  https://github.com/molotovsingh/legal_events_prod/releases"
