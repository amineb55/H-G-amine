# Demo example

`chantier-exemple.jpg` is the photo loaded by the landing page's "Try with an
example" button, so a visitor can test the service without providing their own
image.

The file must be a **real JPEG**: the page uploads it declaring `image/jpeg`,
and the analysis engine receives that type. A PNG renamed to `.jpg` would
declare a type that does not match its content.

To replace it, keep the same name and location — no code change needed:

```bash
python - <<'PY'
from PIL import Image
Image.open("your-photo.png").convert("RGB").save(
    "static/demo/chantier-exemple.jpg", format="JPEG", quality=90, optimize=True)
PY
```
