import re
import urllib.request
from pathlib import Path

FONTS_DIR = Path("src/orion/ui/static/fonts")
FONTS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Download Licenses
orbitron_ofl_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/OFL.txt"
jb_ofl_url = "https://raw.githubusercontent.com/google/fonts/main/ofl/jetbrainsmono/OFL.txt"

print("Downloading Orbitron OFL.txt...")
with urllib.request.urlopen(orbitron_ofl_url) as resp:
    (FONTS_DIR / "OFL-Orbitron.txt").write_bytes(resp.read())
print("Saved OFL-Orbitron.txt")

print("Downloading JetBrains Mono OFL.txt...")
with urllib.request.urlopen(jb_ofl_url) as resp:
    (FONTS_DIR / "OFL-JetBrainsMono.txt").write_bytes(resp.read())
print("Saved OFL-JetBrainsMono.txt")

# 2. Query Google Fonts CSS to get direct woff2 links for latin subset
url = "https://fonts.googleapis.com/css2?family=Orbitron:wght@500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
ua = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
headers = {"User-Agent": ua}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as resp:
    css_content = resp.read().decode("utf-8")

# Parse font-face rules
blocks = css_content.split("@font-face")
downloaded = []

for block in blocks:
    if "/* latin */" not in block:
        continue
    fam_match = re.search(r"font-family:\s*['\"]([^'\"]+)['\"]", block)
    wt_match = re.search(r"font-weight:\s*([^;]+);", block)
    url_match = re.search(r"url\((https://[^)]+\.woff2)\)", block)

    if fam_match and wt_match and url_match:
        family = fam_match.group(1).strip()
        weight = wt_match.group(1).strip()
        font_url = url_match.group(1).strip()

        prefix = "orbitron" if "Orbitron" in family else "jetbrains-mono"
        # If weight is a range e.g. 400 900
        safe_wt = weight.replace(" ", "-")
        filename = f"{prefix}-latin-{safe_wt}.woff2"
        target_path = FONTS_DIR / filename

        if not target_path.exists():
            print(f"Downloading {filename} from {font_url}...")
            with urllib.request.urlopen(font_url) as f_resp:
                target_path.write_bytes(f_resp.read())
            print(f"Saved {filename} ({target_path.stat().st_size} bytes)")
        downloaded.append((family, weight, filename))

print("\nDownloaded Fonts Summary:")
for fam, wt, fn in downloaded:
    print(f"- {fam} (weight: {wt}) -> {fn}")
