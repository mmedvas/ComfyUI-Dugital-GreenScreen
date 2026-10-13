# Dugital Green Screen nodes for ComfyUI

## Install - easiest: from inside ComfyUI
1. In ComfyUI open **Manager** > **Install via Git URL**.
2. Paste: `https://github.com/mmedvas/ComfyUI-Dugital-GreenScreen` and confirm.
3. Restart ComfyUI.
4. Open the folder `ComfyUI\custom_nodes\ComfyUI-Dugital-GreenScreen` and double-click **SET-API-KEY.bat**,
   paste your MiniMax key, press Enter. Restart ComfyUI once more.
5. Open a workflow from **Workflow > Browse Templates**:
   - **Dugital Green Screen**: generate a subject with MiniMax on green, then remove the green.
   - **Dugital Remove Green Screen**: drop in your own green-screen image and remove the green (no MiniMax key needed).

If Manager says Git URL installs are not allowed: open `ComfyUI\user\default\ComfyUI-Manager\config.ini`
(older versions: `ComfyUI\custom_nodes\ComfyUI-Manager\config.ini`),
set `security_level = weak`, restart ComfyUI, install, then set it back to `normal`.

## Install - manual (drag and drop)
Download the repo as ZIP (green **Code** button > Download ZIP), extract it, rename the folder to
`ComfyUI-Dugital-GreenScreen`, drag it into `ComfyUI\custom_nodes`, then do step 4 above.

## Update
Manager > **Custom Nodes Manager** > find *Dugital Green Screen* > **Update**, then restart ComfyUI.

Three nodes (category **Dugital/GreenScreen**):

| Node | What it does |
|---|---|
| **MiniMax Image (Green Screen)** | Generates images with MiniMax `image-01` on a flat chroma-key green (or blue) background. The green-screen instructions are added to your prompt automatically. |
| **Chroma Key (Dugital)** | Removes the green. Outputs a transparent RGBA image, the cleaned subject, and a subject mask. `key_color` = `auto` detects the background colour from the image border. |
| **Green Screen Composite** | Puts the keyed subject on any background image (background is scaled to fill and centre-cropped). |

No extra Python packages are needed (uses numpy, Pillow and torch, which ComfyUI already has).

## API key
Put your MiniMax API key in a file named `minimax_api_key.txt` in this folder (one line, nothing else),
or set the environment variable `MINIMAX_API_KEY`. The key is deliberately NOT a node setting, because
ComfyUI saves node settings inside every output image.

## Tuning the key
- Green edges left on hair or shoulders: raise `despill` to 1.0, or `shrink_edge` to 2.
- Parts of the subject disappear: lower `tolerance`.
- Edges too hard or jagged: raise `feather`.
- Subject has green in it: switch `screen_color` to `blue`.
