VERSION=126.0.6478.164-rpt1
ROOT="$HOME/.local/opt/chromium-$VERSION"

mkdir -p "$ROOT"
cd "$ROOT"

BASE_URL="https://archive.raspberrypi.org/debian/pool/main/c/chromium-browser"

wget "$BASE_URL/chromium-browser_${VERSION}_armhf.deb"
wget "$BASE_URL/chromium-codecs-ffmpeg-extra_${VERSION}_armhf.deb"
wget "$BASE_URL/chromium-chromedriver_${VERSION}_armhf.deb"
wget "$BASE_URL/chromium-browser-l10n_${VERSION}_all.deb"

dpkg-deb -x chromium-browser_${VERSION}_armhf.deb "$ROOT"
dpkg-deb -x chromium-codecs-ffmpeg-extra_${VERSION}_armhf.deb "$ROOT"
dpkg-deb -x chromium-chromedriver_${VERSION}_armhf.deb "$ROOT"
dpkg-deb -x chromium-browser-l10n_${VERSION}_all.deb "$ROOT"

find "$ROOT" -maxdepth 6 -type f -executable \( -name 'chromium-browser' -o -name 'chromium' -o -name 'chromedriver' \)

find "$ROOT" -maxdepth 8 -type f -name 'libffmpeg.so'

mkdir -p "$HOME/.local/bin"

cat > "$HOME/.local/bin/chromium-rpi" << 'EOF'
#!/usr/bin/env bash
VERSION=126.0.6478.164-rpt1
ROOT="$HOME/.local/opt/chromium-$VERSION"
export LD_LIBRARY_PATH="$ROOT/usr/lib/chromium-browser:$ROOT/usr/lib/arm-linux-gnueabihf:$LD_LIBRARY_PATH"
exec "$ROOT/usr/lib/chromium-browser/chromium-browser" "$@"
EOF

chmod +x "$HOME/.local/bin/chromium-rpi"

cat > "$HOME/.local/bin/chromedriver-rpi" << 'EOF'
#!/usr/bin/env bash
VERSION=126.0.6478.164-rpt1
ROOT="$HOME/.local/opt/chromium-$VERSION"

exec "$ROOT/usr/lib/chromium-browser/chromedriver" "$@"
EOF

chmod +x "$HOME/.local/bin/chromedriver-rpi"