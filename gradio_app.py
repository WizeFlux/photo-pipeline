"""Photo Pipeline — Gradio GUI

Run: python gradio_app.py
Opens in browser at http://localhost:7860

Optimized for Apple M1 Ultra with GPU (MPS) acceleration.
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import gradio as gr
import numpy as np
import yaml
from PIL import Image

from pipeline.config import load_config
from pipeline.gpu_ops import gpu_process_from_pil, DEVICE
from pipeline.batch import batch_process_parallel


PROFILES_DIR = Path("profiles")
LUT_DIR = Path("luts")

# ─── Helpers ─────────────────────────────────────────────────────────────────

def list_profiles() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted([f.name for f in PROFILES_DIR.glob("*.yaml")])


def list_luts() -> list[str]:
    if not LUT_DIR.exists():
        return ["None"]
    luts = sorted([str(f) for f in LUT_DIR.glob("*.cube")])
    return ["None"] + luts


def params_from_sliders(
    ev, gamma, highlights, shadows,
    contrast_amount, s_curve, black_point, white_point,
    temperature, tint, saturation, vibrance,
    lut_path, lut_intensity,
) -> dict:
    return {
        "ev": ev, "gamma": gamma,
        "highlights": highlights, "shadows": shadows,
        "contrast_amount": contrast_amount, "s_curve": s_curve,
        "black_point": black_point, "white_point": white_point,
        "temperature": temperature, "tint": tint,
        "saturation": saturation, "vibrance": vibrance,
        "lut_path": lut_path if lut_path != "None" else None,
        "lut_intensity": lut_intensity,
    }


def params_from_config(cfg: dict) -> dict:
    exp = cfg.get("exposure", {})
    con = cfg.get("contrast", {})
    wb = cfg.get("white_balance", {})
    sat = cfg.get("saturation", {})
    lut = cfg.get("lut", {})
    return {
        "ev": exp.get("ev", 0.0), "gamma": exp.get("gamma", 1.0),
        "highlights": exp.get("highlights", 0), "shadows": exp.get("shadows", 0),
        "contrast_amount": con.get("amount", 0), "s_curve": con.get("s_curve", 0),
        "black_point": con.get("black_point", 0), "white_point": con.get("white_point", 255),
        "temperature": wb.get("temperature", 0), "tint": wb.get("tint", 0),
        "saturation": sat.get("amount", 0), "vibrance": sat.get("vibrance", 0),
        "lut_path": lut.get("path"), "lut_intensity": lut.get("intensity", 1.0),
    }


def save_profile(name: str, params: dict, output_cfg: dict | None = None):
    if not name.endswith(".yaml"):
        name = name + ".yaml"
    profile = {
        "exposure": {"ev": params["ev"], "gamma": params["gamma"],
                      "highlights": params["highlights"], "shadows": params["shadows"]},
        "contrast": {"amount": params["contrast_amount"], "s_curve": params["s_curve"],
                      "black_point": params["black_point"], "white_point": params["white_point"]},
        "white_balance": {"temperature": params["temperature"], "tint": params["tint"]},
        "saturation": {"amount": params["saturation"], "vibrance": params["vibrance"]},
        "lut": {"path": params.get("lut_path"), "intensity": params["lut_intensity"]},
    }
    if output_cfg:
        profile["output"] = output_cfg
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / name
    with open(path, "w") as f:
        yaml.dump(profile, f, default_flow_style=False, sort_keys=False)
    return str(path)


def apply_profile_to_sliders(profile_name: str):
    """Load a YAML profile and return slider values."""
    if not profile_name or profile_name == "None":
        return [gr.update()] * 14
    path = PROFILES_DIR / profile_name
    if not path.exists():
        return [gr.update()] * 14
    cfg = load_config(path)
    p = params_from_config(cfg)
    return [
        p["ev"], p["gamma"], p["highlights"], p["shadows"],
        p["contrast_amount"], p["s_curve"], p["black_point"], p["white_point"],
        p["temperature"], p["tint"], p["saturation"], p["vibrance"],
        p["lut_path"] or "None", p["lut_intensity"],
    ]


# ─── Processing ──────────────────────────────────────────────────────────────

def process_preview(
    input_img,
    ev, gamma, highlights, shadows,
    contrast_amount, s_curve, black_point, white_point,
    temperature, tint, saturation, vibrance,
    lut_path, lut_intensity,
    third_profile_name,
):
    """Process image and return: original, live result, profile result (if any)."""
    if input_img is None:
        return None, None, None

    params = params_from_sliders(
        ev, gamma, highlights, shadows,
        contrast_amount, s_curve, black_point, white_point,
        temperature, tint, saturation, vibrance,
        lut_path, lut_intensity,
    )

    # Resize for preview speed
    img = Image.fromarray(input_img) if isinstance(input_img, np.ndarray) else input_img
    if img.mode != "RGB":
        img = img.convert("RGB")

    # Preview at reasonable resolution
    max_w = 1200
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((max_w, int(img.height * ratio)), Image.LANCZOS)

    # Process with GPU
    result_live = gpu_process_from_pil(img, params)

    # Process profile if selected
    result_profile = None
    if third_profile_name and third_profile_name != "None":
        path = PROFILES_DIR / third_profile_name
        if path.exists():
            cfg = load_config(path)
            prof_params = params_from_config(cfg)
            result_profile = gpu_process_from_pil(img, prof_params)

    return np.array(img), np.array(result_live), np.array(result_profile) if result_profile else None


# ─── Profile management ──────────────────────────────────────────────────────

def do_save_profile(name, ev, gamma, highlights, shadows,
                    contrast_amount, s_curve, black_point, white_point,
                    temperature, tint, saturation, vibrance,
                    lut_path, lut_intensity):
    if not name.strip():
        gr.Warning("Enter a profile name")
        return gr.update(), gr.update()
    params = params_from_sliders(
        ev, gamma, highlights, shadows,
        contrast_amount, s_curve, black_point, white_point,
        temperature, tint, saturation, vibrance,
        lut_path, lut_intensity,
    )
    path = save_profile(name.strip(), params)
    gr.Info(f"Saved: {Path(path).name}")
    # Refresh dropdowns
    profiles = list_profiles()
    return gr.update(choices=profiles), gr.update(choices=["None"] + profiles)


def do_delete_profile(name):
    if not name or name == "None":
        gr.Warning("Select a profile to delete")
        return gr.update(), gr.update()
    path = PROFILES_DIR / name
    if path.exists():
        path.unlink()
    gr.Info(f"Deleted: {name}")
    profiles = list_profiles()
    return gr.update(choices=profiles), gr.update(choices=["None"] + profiles)


# ─── Batch processing ────────────────────────────────────────────────────────

def do_batch(input_dir, output_dir, use_gpu,
             ev, gamma, highlights, shadows,
             contrast_amount, s_curve, black_point, white_point,
             temperature, tint, saturation, vibrance,
             lut_path, lut_intensity):
    if not input_dir or not output_dir:
        return "Enter both input and output directories"

    params = params_from_sliders(
        ev, gamma, highlights, shadows,
        contrast_amount, s_curve, black_point, white_point,
        temperature, tint, saturation, vibrance,
        lut_path, lut_intensity,
    )

    results = batch_process_parallel(
        input_dir, output_dir, params,
        max_workers=min(os.cpu_count() or 8, 20),
        use_gpu=use_gpu,
    )

    success = sum(1 for _, o, e in results if o and not e)
    failed = sum(1 for _, _, e in results if e)
    return f"✅ {success} processed, ❌ {failed} failed → {output_dir}"


# ─── Statistics ──────────────────────────────────────────────────────────────

def compute_stats(img_arr) -> dict:
    """Compute image statistics."""
    arr = np.array(img_arr, dtype=np.float64)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return {
        "Brightness": lum.mean(),
        "B_median": np.median(lum),
        "B_std": lum.std(),
        "B_min": lum.min(),
        "B_max": lum.max(),
        "Range": lum.max() - lum.min(),
        "R_mean": r.mean(), "G_mean": g.mean(), "B_mean": b.mean(),
        "R_std": r.std(), "G_std": g.std(), "B_std": b.std(),
        "R/B": r.mean() / max(b.mean(), 1),
        "R/G": r.mean() / max(g.mean(), 1),
        "G/B": g.mean() / max(b.mean(), 1),
        "Saturation": np.std(arr, axis=-1).mean(),
        "SNR": lum.mean() / max(lum.std(), 1),
        "Shadows%": (lum < 50).sum() / lum.size * 100,
        "Midtones%": ((lum >= 50) & (lum < 200)).sum() / lum.size * 100,
        "Highlights%": (lum >= 200).sum() / lum.size * 100,
        "Clip_S%": (arr.min(axis=-1) < 3).sum() / arr.shape[0] / arr.shape[1] * 100,
        "Clip_H%": (arr.max(axis=-1) > 252).sum() / arr.shape[0] / arr.shape[1] * 100,
    }


def stats_to_table(orig, live, profile=None):
    """Build stats comparison table."""
    if orig is None:
        return None
    s_orig = compute_stats(orig)
    s_live = compute_stats(live) if live is not None else {}
    s_prof = compute_stats(profile) if profile is not None else {}

    import pandas as pd
    rows = []
    for key in s_orig:
        row = {"Metric": key, "Original": round(s_orig[key], 2), "Live": round(s_live.get(key, 0), 2)}
        if profile is not None:
            row["Profile"] = round(s_prof.get(key, 0), 2)
        rows.append(row)
    return pd.DataFrame(rows)


# ─── Build Gradio UI ─────────────────────────────────────────────────────────

def build_ui():
    profiles = list_profiles()
    luts = list_luts()
    profile_options = ["None"] + profiles

    with gr.Blocks(title="Photo Pipeline") as app:
        gr.Markdown("# 🖼️ Photo Pipeline")

        # Hide preview in upload widget
        gr.HTML("""
        <style>
        #input_image img { display: none !important; }
        #input_image .toast-wrap { display: block !important; }
        #input_image .upload-container { min-height: 60px !important; }
        </style>
        """)

        # ─── Input (small) + 3 previews in a row ─────────────────────────────
        with gr.Row():
            input_image = gr.Image(label="Input", type="numpy", height=80, width=200, elem_id="input_image", show_fullscreen_button=False)
            third_profile = gr.Dropdown(
                choices=profile_options, value="None",
                label="3rd Preview Profile",
            )

        with gr.Row():
            preview_original = gr.Image(label="Original", interactive=False, height=350)
            preview_live = gr.Image(label="Live Sliders", interactive=False, height=350)
            preview_profile = gr.Image(label="Profile", interactive=False, height=350)

        # ─── Adjustments ─────────────────────────────────────────────────────
        gr.Markdown("### 🎚️ Adjustments")

        with gr.Row():
            with gr.Column():
                gr.Markdown("#### ☀️ Exposure")
                ev = gr.Slider(-3, 3, 0, step=0.01, label="EV")
                gamma = gr.Slider(0.5, 2.5, 1.0, step=0.01, label="Gamma")
                highlights = gr.Slider(-100, 100, 0, step=1, label="Highlights")
                shadows = gr.Slider(-100, 100, 0, step=1, label="Shadows")

            with gr.Column():
                gr.Markdown("#### 📊 Contrast")
                contrast_amount = gr.Slider(-100, 100, 0, step=1, label="Amount")
                s_curve = gr.Slider(0, 100, 0, step=1, label="S-Curve")
                black_point = gr.Slider(0, 50, 0, step=1, label="Black Point")
                white_point = gr.Slider(205, 255, 255, step=1, label="White Point")

            with gr.Column():
                gr.Markdown("#### 🌡️ White Balance")
                temperature = gr.Slider(-100, 100, 0, step=1, label="Temperature")
                tint = gr.Slider(-100, 100, 0, step=1, label="Tint")

                gr.Markdown("#### 🎨 Saturation")
                saturation = gr.Slider(-100, 100, 0, step=1, label="Saturation")
                vibrance = gr.Slider(-100, 100, 0, step=1, label="Vibrance")

            with gr.Column():
                gr.Markdown("#### 🎭 LUT")
                lut_path = gr.Dropdown(choices=luts, value="None", label="LUT File")
                lut_intensity = gr.Slider(0, 1, 1.0, step=0.01, label="Intensity")

        # ─── Profiles ────────────────────────────────────────────────────────
        gr.Markdown("### 📋 Profiles")

        with gr.Row():
            load_profile_dd = gr.Dropdown(choices=profiles, label="YAML → Sliders")
            load_btn = gr.Button("⬆️ Apply", size="sm")

            save_name = gr.Textbox(label="Sliders → YAML", placeholder="profile name")
            save_btn = gr.Button("💾 Save", size="sm")

            delete_profile_dd = gr.Dropdown(choices=profiles, label="Delete")
            delete_btn = gr.Button("🗑️ Delete", size="sm")

        # ─── Statistics ──────────────────────────────────────────────────────
        gr.Markdown("### 📊 Statistics")
        stats_table = gr.Dataframe(
            headers=["Metric", "Original", "Live", "Profile"],
            interactive=False,
            wrap=True,
        )

        # ─── Batch Processing ───────────────────────────────────────────────
        gr.Markdown("### 📁 Batch Process")
        with gr.Row():
            batch_input = gr.Textbox(label="Input directory", placeholder="/path/to/images")
            batch_output = gr.Textbox(label="Output directory", placeholder="/path/to/output")
            batch_gpu = gr.Checkbox(value=True, label="Use GPU")
            batch_btn = gr.Button("Process All", variant="primary")

        batch_status = gr.Textbox(label="Batch Result", interactive=False)

        # ─── Download ───────────────────────────────────────────────────────
        with gr.Row():
            output_format = gr.Dropdown(["jpeg", "webp", "avif", "tiff"], value="jpeg", label="Format")
            output_quality = gr.Slider(1, 100, 90, step=1, label="Quality")
            download_btn = gr.Button("⬇️ Download", variant="primary")

        download_file = gr.File(label="Download", interactive=False)

        # ─── Events ─────────────────────────────────────────────────────────

        all_sliders = [
            ev, gamma, highlights, shadows,
            contrast_amount, s_curve, black_point, white_point,
            temperature, tint, saturation, vibrance,
            lut_path, lut_intensity,
        ]

        # Live preview on any slider change
        for slider in all_sliders:
            slider.change(
                process_preview,
                inputs=[input_image] + all_sliders + [third_profile],
                outputs=[preview_original, preview_live, preview_profile],
            )

        # Also update on image or 3rd profile change
        input_image.change(
            process_preview,
            inputs=[input_image] + all_sliders + [third_profile],
            outputs=[preview_original, preview_live, preview_profile],
        )
        third_profile.change(
            process_preview,
            inputs=[input_image] + all_sliders + [third_profile],
            outputs=[preview_original, preview_live, preview_profile],
        )

        # Update stats when preview changes
        for out in [preview_original, preview_live, preview_profile]:
            out.change(
                stats_to_table,
                inputs=[preview_original, preview_live, preview_profile],
                outputs=[stats_table],
            )

        # Profile management
        load_btn.click(
            apply_profile_to_sliders,
            inputs=[load_profile_dd],
            outputs=all_sliders,
        )

        save_btn.click(
            do_save_profile,
            inputs=[save_name] + all_sliders,
            outputs=[load_profile_dd, third_profile],
        )

        delete_btn.click(
            do_delete_profile,
            inputs=[delete_profile_dd],
            outputs=[delete_profile_dd, third_profile],
        )

        # Batch
        batch_btn.click(
            do_batch,
            inputs=[batch_input, batch_output, batch_gpu] + all_sliders,
            outputs=[batch_status],
        )

        # Download
        def generate_download(input_img, fmt, quality,
                              ev, gamma, highlights, shadows,
                              contrast_amount, s_curve, black_point, white_point,
                              temperature, tint, saturation, vibrance,
                              lut_path, lut_intensity):
            if input_img is None:
                return None
            params = params_from_sliders(
                ev, gamma, highlights, shadows,
                contrast_amount, s_curve, black_point, white_point,
                temperature, tint, saturation, vibrance,
                lut_path, lut_intensity,
            )
            img = Image.fromarray(input_img) if isinstance(input_img, np.ndarray) else input_img
            if img.mode != "RGB":
                img = img.convert("RGB")
            result = gpu_process_from_pil(img, params)

            ext = {"jpeg": "jpg", "webp": "webp", "avif": "avif", "tiff": "tiff"}[fmt]
            pil_fmt = {"jpeg": "JPEG", "webp": "WEBP", "avif": "AVIF", "tiff": "TIFF"}[fmt]

            buf = io.BytesIO()
            save_kwargs = {"quality": quality} if pil_fmt in ("JPEG", "WEBP", "AVIF") else {}
            if pil_fmt == "JPEG":
                save_kwargs["subsampling"] = 0
            result.save(buf, format=pil_fmt, **save_kwargs)

            buf.seek(0)
            return buf

        download_btn.click(
            generate_download,
            inputs=[input_image, output_format, output_quality] + all_sliders,
            outputs=[download_file],
        )

    return app


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Device: {DEVICE}")
    app = build_ui()
    app.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)