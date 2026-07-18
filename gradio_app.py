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
    input_file,
    ev, gamma, highlights, shadows,
    contrast_amount, s_curve, black_point, white_point,
    temperature, tint, saturation, vibrance,
    lut_path, lut_intensity,
    third_profile_name,
):
    """Process image and return: original, live result, profile result (if any)."""
    if input_file is None:
        return None, None, None

    # Load from file path
    img = Image.open(input_file)
    if img.mode != "RGB":
        img = img.convert("RGB")

    params = params_from_sliders(
        ev, gamma, highlights, shadows,
        contrast_amount, s_curve, black_point, white_point,
        temperature, tint, saturation, vibrance,
        lut_path, lut_intensity,
    )

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

import plotly.graph_objects as go
from plotly.subplots import make_subplots

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


def plot_histogram(arr, title):
    """RGB + luminance histogram."""
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    bins = np.arange(0, 257, 1)
    r_hist, _ = np.histogram(r, bins=bins)
    g_hist, _ = np.histogram(g, bins=bins)
    b_hist, _ = np.histogram(b, bins=bins)
    lum_hist, _ = np.histogram(lum, bins=bins)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bins[:-1], y=r_hist, name="R",
                             line=dict(color="red", width=1.5),
                             fill="tozeroy", fillcolor="rgba(255,0,0,0.15)"))
    fig.add_trace(go.Scatter(x=bins[:-1], y=g_hist, name="G",
                             line=dict(color="green", width=1.5),
                             fill="tozeroy", fillcolor="rgba(0,255,0,0.15)"))
    fig.add_trace(go.Scatter(x=bins[:-1], y=b_hist, name="B",
                             line=dict(color="blue", width=1.5),
                             fill="tozeroy", fillcolor="rgba(0,0,255,0.15)"))
    fig.add_trace(go.Scatter(x=bins[:-1], y=lum_hist, name="Lum",
                             line=dict(color="gray", width=1.5, dash="dot")))
    fig.update_layout(
        title=title, xaxis_title="Value (0–255)", yaxis_title="Pixel count",
        height=280, margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_dark",
    )
    return fig


def plot_histograms_row(orig, live, profile=None, profile_name=None):
    """3 histograms in a row (or 2 if no profile)."""
    if orig is None:
        return None

    if profile is not None:
        fig = make_subplots(rows=1, cols=3, subplot_titles=("Original", "Live Sliders", profile_name or "Profile"))
    else:
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Before", "After"))

    def add_hists(fig, arr, col):
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        bins = np.arange(0, 257, 1)
        for ch, name, color in [(r, "R", "red"), (g, "G", "green"), (b, "B", "blue")]:
            h, _ = np.histogram(ch, bins=bins)
            fig.add_trace(go.Scatter(x=bins[:-1], y=h, name=name,
                                     line=dict(color=color, width=1),
                                     fill="tozeroy", fillcolor=color.replace("red", "rgba(255,0,0,0.1)").replace("green", "rgba(0,255,0,0.1)").replace("blue", "rgba(0,0,255,0.1)")),
                         row=1, col=col)
        lh, _ = np.histogram(lum, bins=bins)
        fig.add_trace(go.Scatter(x=bins[:-1], y=lh, name="Lum",
                                 line=dict(color="gray", width=1, dash="dot")),
                     row=1, col=col)

    add_hists(fig, np.array(orig, dtype=np.float64), 1)
    add_hists(fig, np.array(live, dtype=np.float64), 2)
    if profile is not None:
        add_hists(fig, np.array(profile, dtype=np.float64), 3)

    fig.update_layout(height=300, showlegend=False, template="plotly_dark",
                      margin=dict(l=20, r=20, t=50, b=40))
    return fig


def plot_channel_deltas(orig, live, profile=None, profile_name=None):
    """Channel deltas: (After - Original) per channel."""
    if orig is None:
        return None

    bins = np.arange(0, 257, 1)
    channels = [("Red", "#ff4444", "rgba(255,68,68,0.2)"),
                ("Green", "#44ff44", "rgba(68,255,68,0.2)"),
                ("Blue", "#4488ff", "rgba(68,136,255,0.2)")]

    orig_arr = np.array(orig, dtype=np.float64)
    live_arr = np.array(live, dtype=np.float64)

    if profile is not None:
        fig = make_subplots(rows=1, cols=2, subplot_titles=("Live − Original", f"{profile_name} − Original"))
    else:
        fig = make_subplots(rows=1, cols=1, subplot_titles=("Live − Original",))

    def add_deltas(fig, arr_b, col):
        for i, (name, color, fill) in enumerate(channels):
            orig_h, _ = np.histogram(orig_arr[..., i], bins=bins)
            b_h, _ = np.histogram(arr_b[..., i], bins=bins)
            delta = b_h.astype(np.float64) - orig_h.astype(np.float64)
            fig.add_trace(go.Scatter(
                x=bins[:-1], y=delta, name=name,
                line=dict(color=color, width=2),
                fill="tozeroy", fillcolor=fill,
            ), row=1, col=col)

    add_deltas(fig, live_arr, 1)
    if profile is not None:
        add_deltas(fig, np.array(profile, dtype=np.float64), 2)

    fig.update_layout(height=320, template="plotly_dark",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                      margin=dict(l=30, r=20, t=50, b=40))
    return fig


def compute_curve(ev, gamma, contrast, s_curve, bp, wp):
    """Compute tone curve."""
    x = np.linspace(0, 255, 256)
    y = x.copy().astype(np.float64)
    y = y * (2.0 ** ev)
    y = np.clip(y / 255.0, 0, 1) ** (1.0 / gamma) * 255.0
    if bp > 0:
        y = np.where(y < bp, 0, (y - bp) * 255.0 / (255 - bp))
    if wp < 255:
        y = np.where(y > wp, 255, y * 255.0 / wp)
    if contrast != 0:
        factor = 1.0 + contrast / 100.0
        y = 128.0 + (y - 128.0) * factor
    if s_curve > 0:
        strength = s_curve / 100.0
        norm = np.clip(y / 255.0, 0, 1)
        k = 5.0 * strength
        sigmoid = 1.0 / (1.0 + np.exp(-k * (norm - 0.5)))
        y = (norm * (1 - strength) + sigmoid * strength) * 255.0
    return x, np.clip(y, 0, 255)


def plot_tone_curve(params, third_params=None, profile_name=None):
    """Tone curve: input → output."""
    x, y_live = compute_curve(
        params["ev"], params["gamma"], params["contrast_amount"],
        params["s_curve"], params["black_point"], params["white_point"],
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=x, name="Identity",
                             line=dict(color="gray", width=1, dash="dot")))
    fig.add_trace(go.Scatter(x=x, y=y_live, name="Live Curve",
                             line=dict(color="#00d4aa", width=2.5)))
    if third_params is not None:
        _, y_prof = compute_curve(
            third_params["ev"], third_params["gamma"], third_params["contrast_amount"],
            third_params["s_curve"], third_params["black_point"], third_params["white_point"],
        )
        fig.add_trace(go.Scatter(x=x, y=y_prof, name=f"{profile_name} Curve",
                                 line=dict(color="#ff9900", width=2, dash="dash")))
    fig.update_layout(
        xaxis_title="Input", yaxis_title="Output", height=300,
        margin=dict(l=40, r=20, t=30, b=40), template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def compute_all_plots(orig, live, profile, profile_name, params, third_params):
    """Generate all 3 plots at once."""
    if orig is None:
        return None, None, None

    # Histograms
    hist_fig = plot_histograms_row(orig, live, profile, profile_name)

    # Channel deltas
    delta_fig = plot_channel_deltas(orig, live, profile, profile_name)

    # Tone curve
    curve_fig = plot_tone_curve(params, third_params, profile_name)

    return hist_fig, delta_fig, curve_fig


# ─── Build Gradio UI ─────────────────────────────────────────────────────────

def build_ui():
    profiles = list_profiles()
    luts = list_luts()
    profile_options = ["None"] + profiles

    with gr.Blocks(title="Photo Pipeline") as app:
        gr.Markdown("# 🖼️ Photo Pipeline")

        # ─── Input + 3 previews in a row ──────────────────────────────────────
        with gr.Row():
            input_file = gr.File(label="Upload image", file_types=["image"], height=80)
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

        gr.Markdown("### 📈 Histograms")
        plot_histograms = gr.Plot()

        gr.Markdown("### 📊 Channel Deltas")
        plot_deltas = gr.Plot()

        gr.Markdown("### 📈 Tone Curve")
        plot_tone = gr.Plot()

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
                inputs=[input_file] + all_sliders + [third_profile],
                outputs=[preview_original, preview_live, preview_profile],
            )

        # Also update on image or 3rd profile change
        input_file.change(
            process_preview,
            inputs=[input_file] + all_sliders + [third_profile],
            outputs=[preview_original, preview_live, preview_profile],
        )
        third_profile.change(
            process_preview,
            inputs=[input_file] + all_sliders + [third_profile],
            outputs=[preview_original, preview_live, preview_profile],
        )

        # Update stats + plots when preview changes
        def update_stats_and_plots(orig, live, profile, profile_name,
                                    ev, gamma, highlights, shadows,
                                    contrast_amount, s_curve, black_point, white_point,
                                    temperature, tint, saturation, vibrance,
                                    lut_path, lut_intensity):
            if orig is None:
                return None, None, None, None, None

            # Stats table
            table = stats_to_table(orig, live, profile)

            # Plots
            params = params_from_sliders(
                ev, gamma, highlights, shadows,
                contrast_amount, s_curve, black_point, white_point,
                temperature, tint, saturation, vibrance,
                lut_path, lut_intensity,
            )

            third_params = None
            if profile_name and profile_name != "None":
                path = PROFILES_DIR / profile_name
                if path.exists():
                    cfg = load_config(path)
                    third_params = params_from_config(cfg)

            hist_fig, delta_fig, curve_fig = compute_all_plots(
                orig, live, profile, profile_name, params, third_params
            )

            return table, hist_fig, delta_fig, curve_fig

        stats_inputs = [
            preview_original, preview_live, preview_profile, third_profile,
        ] + all_sliders
        stats_outputs = [stats_table, plot_histograms, plot_deltas, plot_tone]

        for out in [preview_original, preview_live, preview_profile]:
            out.change(
                update_stats_and_plots,
                inputs=stats_inputs,
                outputs=stats_outputs,
            )
        third_profile.change(
            update_stats_and_plots,
            inputs=stats_inputs,
            outputs=stats_outputs,
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
        def generate_download(input_file, fmt, quality,
                              ev, gamma, highlights, shadows,
                              contrast_amount, s_curve, black_point, white_point,
                              temperature, tint, saturation, vibrance,
                              lut_path, lut_intensity):
            if input_file is None:
                return None
            params = params_from_sliders(
                ev, gamma, highlights, shadows,
                contrast_amount, s_curve, black_point, white_point,
                temperature, tint, saturation, vibrance,
                lut_path, lut_intensity,
            )
            img = Image.open(input_file)
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
            inputs=[input_file, output_format, output_quality] + all_sliders,
            outputs=[download_file],
        )

    return app


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"Device: {DEVICE}")
    app = build_ui()
    app.launch(server_name="127.0.0.1", server_port=7860, inbrowser=True)