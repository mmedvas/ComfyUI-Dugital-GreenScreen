"""Pure-numpy keying helpers (no torch), so they can be tested on their own.
All images are float32 arrays in [0, 1], shape (H, W, 3); masks are (H, W)."""
import numpy as np

NAMED = {"green": (0.0, 1.0, 0.0), "blue": (0.0, 0.0, 1.0)}


def _ycbcr_chroma(rgb):
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    cb = 0.5 - 0.168736 * r - 0.331264 * g + 0.5 * b
    cr = 0.5 + 0.5 * r - 0.418688 * g - 0.081312 * b
    return cb, cr


def parse_key_color(text):
    """'#00FF00', '00ff00', 'green', 'blue' -> (r, g, b) in 0..1, or None for 'auto'."""
    t = (text or "auto").strip().lower()
    if t in ("", "auto"):
        return None
    if t in NAMED:
        return NAMED[t]
    t = t.lstrip("#")
    if len(t) == 6:
        try:
            return tuple(int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        except ValueError:
            pass
    raise ValueError(f"key_color must be 'auto', 'green', 'blue' or a hex colour like #00FF00, got {text!r}")


def auto_key_color(rgb, band=0.03):
    """Median colour of the image border - the background on a green-screen shot."""
    h, w, _ = rgb.shape
    bh, bw = max(1, int(h * band)), max(1, int(w * band))
    border = np.concatenate([
        rgb[:bh].reshape(-1, 3), rgb[-bh:].reshape(-1, 3),
        rgb[:, :bw].reshape(-1, 3), rgb[:, -bw:].reshape(-1, 3)])
    return tuple(float(x) for x in np.median(border, axis=0))


def _erode(mask, px):
    m = mask
    for _ in range(int(px)):
        p = np.pad(m, 1, mode="edge")
        m = np.minimum.reduce([p[1:-1, 1:-1], p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
    return m


def _blur(mask, sigma):
    if sigma <= 0:
        return mask
    r = max(1, int(round(sigma * 3)))
    x = np.arange(-r, r + 1, dtype=np.float32)
    k = np.exp(-(x * x) / (2 * sigma * sigma))
    k /= k.sum()
    p = np.pad(mask, ((r, r), (0, 0)), mode="edge")
    m = sum(k[i] * p[i:i + mask.shape[0]] for i in range(len(k)))
    p = np.pad(m, ((0, 0), (r, r)), mode="edge")
    return sum(k[i] * p[:, i:i + mask.shape[1]] for i in range(len(k)))


def chroma_key(rgb, key_rgb=None, tolerance=0.12, softness=0.10, despill=0.8, shrink_edge=1, feather=1.0):
    """Returns (despilled_rgb, alpha, key_rgb_used). alpha: 1 = subject, 0 = background."""
    rgb = np.clip(rgb.astype(np.float32), 0.0, 1.0)
    if key_rgb is None:
        key_rgb = auto_key_color(rgb)
    k = np.array(key_rgb, dtype=np.float32).reshape(1, 1, 3)

    cb, cr = _ycbcr_chroma(rgb)
    kcb, kcr = _ycbcr_chroma(k)
    dist = np.sqrt((cb - kcb[0, 0]) ** 2 + (cr - kcr[0, 0]) ** 2)
    alpha = np.clip((dist - tolerance) / max(softness, 1e-4), 0.0, 1.0)

    if shrink_edge > 0:
        alpha = _erode(alpha, shrink_edge)
    if feather > 0:
        alpha = _blur(alpha, feather)
    alpha = np.clip(alpha, 0.0, 1.0).astype(np.float32)

    out = rgb.copy()
    if despill > 0:
        dom = int(np.argmax(k[0, 0]))  # 1 = green screen, 2 = blue screen
        if dom in (1, 2):
            others = [c for c in (0, 1, 2) if c != dom]
            limit = np.maximum(out[..., others[0]], out[..., others[1]])
            excess = np.maximum(out[..., dom] - limit, 0.0)
            out[..., dom] = out[..., dom] - despill * excess
    return np.clip(out, 0.0, 1.0), alpha, tuple(float(x) for x in k[0, 0])


def fit_cover(bg_rgb, h, w):
    """Resize + centre-crop a background to exactly (h, w), keeping its proportions."""
    from PIL import Image
    im = Image.fromarray((np.clip(bg_rgb, 0, 1) * 255).astype(np.uint8))
    bw, bh = im.size
    scale = max(w / bw, h / bh)
    nw, nh = max(w, round(bw * scale)), max(h, round(bh * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - w) // 2, (nh - h) // 2
    im = im.crop((left, top, left + w, top + h))
    return np.asarray(im).astype(np.float32) / 255.0


def composite(fg_rgb, alpha, bg_rgb):
    bg = fit_cover(bg_rgb, fg_rgb.shape[0], fg_rgb.shape[1])
    a = alpha[..., None]
    return fg_rgb * a + bg * (1.0 - a)
