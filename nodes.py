import base64
import io
import json
import os
import random
import urllib.error
import urllib.request

import numpy as np
import torch
from PIL import Image

from . import keying

HERE = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(HERE, "minimax_api_key.txt")

ENDPOINTS = {
    "global (api.minimax.io)": "https://api.minimax.io/v1/image_generation",
    "china (api.minimaxi.com)": "https://api.minimaxi.com/v1/image_generation",
}
ASPECTS = ["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"]
SCREEN = {
    "green": "Isolated on a solid, flat, evenly lit pure chroma-key green background (#00FF00). "
             "Plain studio green screen, no gradient, no texture, no shadows on the background. "
             "The subject is fully in frame with clean, sharp edges and does not wear or hold anything green.",
    "blue": "Isolated on a solid, flat, evenly lit pure chroma-key blue background (#0000FF). "
            "Plain studio blue screen, no gradient, no texture, no shadows on the background. "
            "The subject is fully in frame with clean, sharp edges and does not wear or hold anything blue.",
}
ERRORS = {
    1002: "MiniMax rate limit reached - wait a moment and try again.",
    1004: "MiniMax rejected the API key (authentication failed).",
    1008: "MiniMax account balance is too low - top up credits on platform.minimax.io.",
    1026: "MiniMax blocked the prompt as sensitive content - rephrase it.",
    2013: "MiniMax says a parameter is invalid.",
    2049: "MiniMax says the API key is invalid.",
}


def _api_key():
    k = os.environ.get("MINIMAX_API_KEY", "").strip()
    if k:
        return k
    for path in (KEY_FILE, os.path.expanduser("~/.minimax_api_key")):
        if os.path.exists(path):
            k = open(path, encoding="utf-8-sig").read().strip().strip("\ufeff")
            if k:
                return k
    raise RuntimeError(
        "No MiniMax API key found. Put your key in this file (one line, nothing else):\n"
        f"  {KEY_FILE}\nor set the MINIMAX_API_KEY environment variable, then restart ComfyUI.")


def _to_tensor(np_imgs):
    return torch.from_numpy(np.stack(np_imgs).astype(np.float32))


class MiniMaxImageGreenScreen:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "prompt": ("STRING", {"multiline": True, "default": "A news presenter in a navy suit, standing, front view, waist up, studio lighting"}),
            "screen_color": (list(SCREEN.keys()), {"default": "green"}),
            "aspect_ratio": (ASPECTS, {"default": "9:16"}),
            "images": ("INT", {"default": 1, "min": 1, "max": 9}),
            "seed": ("INT", {"default": 0, "min": 0, "max": 2147483647}),
            "prompt_optimizer": ("BOOLEAN", {"default": False}),
            "region": (list(ENDPOINTS.keys()), {"default": "global (api.minimax.io)"}),
        }}

    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("image", "final_prompt")
    FUNCTION = "generate"
    CATEGORY = "Dugital/GreenScreen"

    def generate(self, prompt, screen_color, aspect_ratio, images, seed, prompt_optimizer, region):
        final_prompt = f"{prompt.strip()}. {SCREEN[screen_color]}"[:1500]
        body = {"model": "image-01", "prompt": final_prompt, "aspect_ratio": aspect_ratio,
                "response_format": "base64", "n": int(images),
                "seed": int(seed) if seed > 0 else random.randint(1, 2147483647),
                "prompt_optimizer": bool(prompt_optimizer)}
        req = urllib.request.Request(ENDPOINTS[region], data=json.dumps(body).encode("utf-8"), headers={
            "Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"MiniMax HTTP {e.code}: {e.read()[:300]!r}")

        status = (data.get("base_resp") or {}).get("status_code", -1)
        if status != 0:
            msg = ERRORS.get(status, (data.get("base_resp") or {}).get("status_msg", "unknown error"))
            raise RuntimeError(f"MiniMax error {status}: {msg}")

        b64s = (data.get("data") or {}).get("image_base64") or []
        if not b64s:
            raise RuntimeError("MiniMax returned no images (all may have been blocked by its content filter).")
        out = []
        for b in b64s:
            im = Image.open(io.BytesIO(base64.b64decode(b))).convert("RGB")
            out.append(np.asarray(im).astype(np.float32) / 255.0)
        if len({a.shape for a in out}) > 1:  # keep the batch uniform
            h, w = out[0].shape[:2]
            out = [a if a.shape[:2] == (h, w) else
                   np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((w, h))).astype(np.float32) / 255.0
                   for a in out]
        return (_to_tensor(out), final_prompt)


class ChromaKeyDugital:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "image": ("IMAGE",),
            "key_color": ("STRING", {"default": "auto"}),
            "tolerance": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 0.6, "step": 0.01}),
            "softness": ("FLOAT", {"default": 0.10, "min": 0.0, "max": 0.5, "step": 0.01}),
            "despill": ("FLOAT", {"default": 0.8, "min": 0.0, "max": 1.0, "step": 0.05}),
            "shrink_edge": ("INT", {"default": 1, "min": 0, "max": 10}),
            "feather": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 10.0, "step": 0.1}),
        }}

    RETURN_TYPES = ("IMAGE", "IMAGE", "MASK", "STRING")
    RETURN_NAMES = ("transparent_rgba", "subject_rgb", "subject_mask", "key_used")
    FUNCTION = "key"
    CATEGORY = "Dugital/GreenScreen"

    def key(self, image, key_color, tolerance, softness, despill, shrink_edge, feather):
        fixed = keying.parse_key_color(key_color)
        rgba, rgb, masks, used = [], [], [], None
        for frame in image.cpu().numpy():
            out, alpha, used = keying.chroma_key(frame[..., :3], fixed, tolerance, softness, despill, shrink_edge, feather)
            rgb.append(out)
            masks.append(alpha)
            rgba.append(np.concatenate([out, alpha[..., None]], axis=-1))
        used_hex = "#%02X%02X%02X" % tuple(int(round(c * 255)) for c in used)
        return (_to_tensor(rgba), _to_tensor(rgb), torch.from_numpy(np.stack(masks)), used_hex)


class GreenScreenCompositeDugital:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "subject_rgb": ("IMAGE",),
            "subject_mask": ("MASK",),
            "background": ("IMAGE",),
        }}

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "composite"
    CATEGORY = "Dugital/GreenScreen"

    def composite(self, subject_rgb, subject_mask, background):
        fg = subject_rgb.cpu().numpy()
        m = subject_mask.cpu().numpy()
        bg = background.cpu().numpy()
        out = []
        for i in range(fg.shape[0]):
            out.append(keying.composite(fg[i][..., :3], m[min(i, len(m) - 1)], bg[min(i, len(bg) - 1)][..., :3]))
        return (_to_tensor(out),)


NODE_CLASS_MAPPINGS = {
    "DugitalMiniMaxImageGreenScreen": MiniMaxImageGreenScreen,
    "DugitalChromaKey": ChromaKeyDugital,
    "DugitalGreenScreenComposite": GreenScreenCompositeDugital,
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "DugitalMiniMaxImageGreenScreen": "MiniMax Image (Green Screen)",
    "DugitalChromaKey": "Chroma Key (Dugital)",
    "DugitalGreenScreenComposite": "Green Screen Composite",
}
