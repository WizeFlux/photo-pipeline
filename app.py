"""Photo Pipeline — Streamlit GUI

Run: streamlit run app.py
Opens in browser at http://localhost:8501
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image

from pipeline.config import load_config
from pipeline.ops.crop import crop_image
from pipeline.ops.exposure import apply_exposure
from pipeline.ops.contrast import apply_contrast
from pipeline.ops.white_balance import apply_white_balance
from pipeline.ops.saturation import apply_saturation
from pipeline.ops.lut import apply_lut


# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Photo Pipeline",
    page_icon="🖼️",
    layout="wide",
)


# ─── Session State ───────────────────────────────────────────────────────────

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

@st.cache_data(max_entries=1)
def load_image_bytes(data: bytes) -> Image.Image:
    """Load PIL image from bytes."""
    img = Image.open(io.BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def process_single(img: Image.Image, params: dict) -> Image.Image:
    """Apply all ops to a single image (for live preview)."""
    arr = np.array(img, dtype=np.float32)

    # Exposure
    arr = apply_exposure(
        arr, ev=params["ev"], gamma=params["gamma"],
        highlights=params["highlights"], shadows=params["shadows"],
    )
    # Contrast
    arr = apply_contrast(
        arr, amount=params["contrast_amount"],
        s_curve=params["s_curve"],
        black_point=params["black_point"],
        white_point=params["white_point"],
    )
    # White balance
    arr = apply_white_balance(arr, temperature=params["temperature"], tint=params["tint"])
    # Saturation
    arr = apply_saturation(arr, amount=params["saturation"], vibrance=params["vibrance"])
    # LUT
    if params.get("lut_path"):
        arr = apply_lut(arr, params["lut_path"], params["lut_intensity"])

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def img_to_bytes(img: Image.Image, fmt: str = "JPEG", quality: int = 90) -> bytes:
    """Convert PIL image to bytes for display."""
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()


def build_params_from_ui() -> dict:
    """Collect all parameters from Streamlit widgets."""
    return {
        "ev": st.session_state.ev,
        "gamma": st.session_state.gamma,
        "highlights": st.session_state.highlights,
        "shadows": st.session_state.shadows,
        "contrast_amount": st.session_state.contrast_amount,
        "s_curve": st.session_state.s_curve,
        "black_point": st.session_state.black_point,
        "white_point": st.session_state.white_point,
        "temperature": st.session_state.temperature,
        "tint": st.session_state.tint,
        "saturation": st.session_state.saturation,
        "vibrance": st.session_state.vibrance,
        "lut_path": st.session_state.lut_path if st.session_state.lut_path != "None" else None,
        "lut_intensity": st.session_state.lut_intensity,
    }


# ─── Reset helpers ───────────────────────────────────────────────────────────

DEFAULTS = {
    "ev": 0.0,
    "gamma": 1.0,
    "highlights": 0,
    "shadows": 0,
    "contrast_amount": 0,
    "s_curve": 0,
    "black_point": 0,
    "white_point": 255,
    "temperature": 0,
    "tint": 0,
    "saturation": 0,
    "vibrance": 0,
    "lut_intensity": 1.0,
}


def reset_value(key: str):
    """Reset a session state key to its default."""
    st.session_state[key] = DEFAULTS[key]


def slider_with_reset(label, key, min_val, max_val, default, step, fmt=None):
    """Render a slider with a reset button next to it."""
    col_s, col_r = st.columns([5, 1])
    with col_s:
        st.slider(label, min_val, max_val, default, step, key=key, format=fmt)
    with col_r:
        st.button("↺", key=f"reset_{key}", on_click=reset_value, args=(key,),
                  help=f"Reset to {default}")


# ─── UI Layout ───────────────────────────────────────────────────────────────

st.title("🖼️ Photo Pipeline")
st.markdown("Color grading with LUTs — live preview.")

# ─── File Upload ─────────────────────────────────────────────────────────────

col_upload, col_profile = st.columns([3, 2])

with col_upload:
    uploaded = st.file_uploader(
        "Upload image for preview",
        type=["tiff", "tif", "jpg", "jpeg", "png", "webp"],
        help="Drag and drop an image to see live preview of all adjustments",
    )
    if uploaded:
        st.session_state.uploaded_file = uploaded.getvalue()

with col_profile:
    profile_files = list(Path("profiles").glob("*.yaml")) if Path("profiles").exists() else []
    profile_names = ["None (defaults)"] + [f.name for f in profile_files]
    selected_profile = st.selectbox("Profile", profile_names, index=0)

# LUT files
lut_dir = Path("luts")
lut_files = ["None"] + [str(f) for f in lut_dir.glob("*.cube")] if lut_dir.exists() else ["None"]

# ─── Sidebar: All Controls ───────────────────────────────────────────────────

st.sidebar.markdown("### 🎚️ Adjustments")

# Exposure
st.sidebar.markdown("#### ☀️ Exposure")
slider_with_reset("Exposure (EV)", "ev", -3.0, 3.0, 0.0, 0.01, "%.2f")
slider_with_reset("Gamma", "gamma", 0.5, 2.5, 1.0, 0.01, "%.2f")
slider_with_reset("Highlights", "highlights", -100, 100, 0, 1)
slider_with_reset("Shadows", "shadows", -100, 100, 0, 1)

# Contrast
st.sidebar.markdown("#### 📊 Contrast")
slider_with_reset("Amount", "contrast_amount", -100, 100, 0, 1)
slider_with_reset("S-Curve", "s_curve", 0, 100, 0, 1)
slider_with_reset("Black Point", "black_point", 0, 50, 0, 1)
slider_with_reset("White Point", "white_point", 205, 255, 255, 1)

# White Balance
st.sidebar.markdown("#### 🌡️ White Balance")
slider_with_reset("Temperature", "temperature", -100, 100, 0, 1)
slider_with_reset("Tint", "tint", -100, 100, 0, 1)

# Saturation
st.sidebar.markdown("#### 🎨 Saturation")
slider_with_reset("Saturation", "saturation", -100, 100, 0, 1)
slider_with_reset("Vibrance", "vibrance", -100, 100, 0, 1)

# LUT
st.sidebar.markdown("#### 🎭 LUT")
st.sidebar.selectbox("LUT File", lut_files, key="lut_path", index=0)
slider_with_reset("LUT Intensity", "lut_intensity", 0.0, 1.0, 1.0, 0.01, "%.2f")

# Reset all
st.sidebar.markdown("---")
if st.sidebar.button("🔄 Reset All"):
    for k in DEFAULTS:
        st.session_state[k] = DEFAULTS[k]
    st.rerun()

# Output
st.sidebar.markdown("### 💾 Output")
st.sidebar.selectbox("Format", ["jpeg", "webp", "avif", "tiff"],
                     key="output_format", index=0)
st.sidebar.slider("Quality", 1, 100, 90, key="output_quality")
st.sidebar.number_input("Width (px)", value=0, step=100,
                        help="0 = original size", key="output_width")

# ─── Load profile defaults ───────────────────────────────────────────────────

if selected_profile != "None (defaults)":
    prof_path = Path("profiles") / selected_profile
    if prof_path.exists():
        load_config(prof_path)  # validates profile loads

# ─── Main: Preview ───────────────────────────────────────────────────────────

if st.session_state.uploaded_file:
    img = load_image_bytes(st.session_state.uploaded_file)
    params = build_params_from_ui()

    # Process for preview (resize down for speed)
    preview_w = 900
    w, h = img.size
    if w > preview_w:
        preview_h = int(h * preview_w / w)
        img_preview = img.resize((preview_w, preview_h), Image.LANCZOS)
    else:
        img_preview = img

    # Process
    with st.spinner("Processing..."):
        result = process_single(img_preview, params)

    # Show before/after
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Before")
        st.image(img_preview, width='stretch')
    with col2:
        st.markdown("#### After")
        st.image(result, width='stretch')

    # Download button
    st.markdown("---")
    dl_col1, dl_col2 = st.columns([1, 3])
    with dl_col1:
        fmt = st.session_state.output_format
        quality = st.session_state.output_quality
        ext = {"jpeg": "jpg", "webp": "webp", "avif": "avif", "tiff": "tiff"}[fmt]
        pil_fmt = {"jpeg": "JPEG", "webp": "WEBP", "avif": "AVIF", "tiff": "TIFF"}[fmt]

        full_result = process_single(img, params)
        if st.session_state.output_width > 0:
            ow, oh = full_result.size
            new_h = int(oh * st.session_state.output_width / ow)
            full_result = full_result.resize(
                (st.session_state.output_width, new_h), Image.LANCZOS
            )

        buf = io.BytesIO()
        save_kwargs = {"quality": quality} if pil_fmt in ("JPEG", "WEBP", "AVIF") else {}
        if pil_fmt == "JPEG":
            save_kwargs["subsampling"] = 0
        full_result.save(buf, format=pil_fmt, **save_kwargs)

        st.download_button(
            f"⬇️ Download ({ext.upper()})",
            data=buf.getvalue(),
            file_name=f"processed.{ext}",
            mime=f"image/{fmt}",
        )

    with dl_col2:
        st.info("💡 Adjust sliders in the sidebar → preview updates in real-time. "
                "Download the full-resolution result when satisfied.")

    # ─── Image Statistics ─────────────────────────────────────────────────────

    st.markdown("---")
    st.markdown("### 📊 Image Statistics")

    orig_arr = np.array(img_preview, dtype=np.float64)
    proc_arr = np.array(result, dtype=np.float64)

    # Per-channel stats
    def channel_stats(arr, label):
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        lum = 0.299 * r + 0.587 * g + 0.114 * b
        return {
            "label": label,
            "brightness": lum.mean(),
            "brightness_std": lum.std(),
            "brightness_min": lum.min(),
            "brightness_max": lum.max(),
            "brightness_median": np.median(lum),
            "r_mean": r.mean(), "r_std": r.std(),
            "g_mean": g.mean(), "g_std": g.std(),
            "b_mean": b.mean(), "b_std": b.std(),
            "rb_ratio": r.mean() / max(b.mean(), 1),
            "rg_ratio": r.mean() / max(g.mean(), 1),
            "gb_ratio": g.mean() / max(b.mean(), 1),
            "saturation_mean": np.std(arr, axis=-1).mean(),
            "contrast_mean": lum.std(),
            "shadow_pct": (lum < 50).sum() / lum.size * 100,
            "midtone_pct": ((lum >= 50) & (lum < 200)).sum() / lum.size * 100,
            "highlight_pct": (lum >= 200).sum() / lum.size * 100,
            "clipped_shadows": (arr.min(axis=-1) < 3).sum() / arr.shape[0] / arr.shape[1] * 100,
            "clipped_highlights": (arr.max(axis=-1) > 252).sum() / arr.shape[0] / arr.shape[1] * 100,
            "dynamic_range": lum.max() - lum.min(),
            "snr": lum.mean() / max(lum.std(), 1),
        }

    orig_stats = channel_stats(orig_arr, "Before")
    proc_stats = channel_stats(proc_arr, "After")

    # ─── Numeric comparison table ─────────────────────────────────────────────

    stat_rows = [
        ("Brightness (mean)", ".1f"),
        ("Brightness (median)", ".1f"),
        ("Brightness (std)", ".1f"),
        ("Brightness (min)", ".1f"),
        ("Brightness (max)", ".1f"),
        ("Brightness (range)", ".1f"),
        ("Contrast (lum std)", ".1f"),
        ("R mean", ".1f"),
        ("G mean", ".1f"),
        ("B mean", ".1f"),
        ("R std", ".1f"),
        ("G std", ".1f"),
        ("B std", ".1f"),
        ("R/B ratio", ".3f"),
        ("R/G ratio", ".3f"),
        ("G/B ratio", ".3f"),
        ("Saturation (mean)", ".1f"),
        ("SNR (mean/std)", ".2f"),
        ("Shadows <50 (%)", ".1f"),
        ("Midtones 50-200 (%)", ".1f"),
        ("Highlights ≥200 (%)", ".1f"),
        ("Clipped shadows (%)", ".2f"),
        ("Clipped highlights (%)", ".2f"),
    ]

    key_map = {
        "Brightness (mean)": "brightness",
        "Brightness (median)": "brightness_median",
        "Brightness (std)": "brightness_std",
        "Brightness (min)": "brightness_min",
        "Brightness (max)": "brightness_max",
        "Brightness (range)": "dynamic_range",
        "Contrast (lum std)": "contrast_mean",
        "R mean": "r_mean",
        "G mean": "g_mean",
        "B mean": "b_mean",
        "R std": "r_std",
        "G std": "g_std",
        "B std": "b_std",
        "R/B ratio": "rb_ratio",
        "R/G ratio": "rg_ratio",
        "G/B ratio": "gb_ratio",
        "Saturation (mean)": "saturation_mean",
        "SNR (mean/std)": "snr",
        "Shadows <50 (%)": "shadow_pct",
        "Midtones 50-200 (%)": "midtone_pct",
        "Highlights ≥200 (%)": "highlight_pct",
        "Clipped shadows (%)": "clipped_shadows",
        "Clipped highlights (%)": "clipped_highlights",
    }

    import pandas as pd
    rows = []
    for label, fmt in stat_rows:
        key = key_map[label]
        before_val = orig_stats[key]
        after_val = proc_stats[key]
        delta = after_val - before_val
        rows.append({
            "Metric": label,
            "Before": format(before_val, fmt),
            "After": format(after_val, fmt),
            "Δ": format(delta, fmt),
        })

    st.dataframe(pd.DataFrame(rows), width='stretch', hide_index=True)

    # ─── Histograms ───────────────────────────────────────────────────────────

    st.markdown("#### Histograms")

    hist_col1, hist_col2 = st.columns(2)

    def plot_histogram(arr, title, ax_key):
        """Plot RGB + luminance histograms using Streamlit."""
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

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
            title=title,
            xaxis_title="Value (0–255)",
            yaxis_title="Pixel count",
            height=300,
            margin=dict(l=40, r=20, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_dark",
        )
        return fig

    with hist_col1:
        st.plotly_chart(plot_histogram(orig_arr, "Before — RGB Histograms", "before"),
                        width='stretch')
    with hist_col2:
        st.plotly_chart(plot_histogram(proc_arr, "After — RGB Histograms", "after"),
                        width='stretch')

    # ─── Per-channel comparison ───────────────────────────────────────────────

    st.markdown("#### Per-Channel Comparison")

    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    fig2 = make_subplots(rows=1, cols=3, subplot_titles=("Red", "Green", "Blue"))
    bins = np.arange(0, 257, 1)

    for i, (ch_name, color) in enumerate(["Red", "red"], ["Green", "green"], ["Blue", "blue"]):
        orig_hist, _ = np.histogram(orig_arr[..., i], bins=bins)
        proc_hist, _ = np.histogram(proc_arr[..., i], bins=bins)
        fig2.add_trace(go.Scatter(x=bins[:-1], y=orig_hist, name=f"{ch_name} before",
                                  line=dict(color=color, width=1.5, dash="dot")),
                       row=1, col=i+1)
        fig2.add_trace(go.Scatter(x=bins[:-1], y=proc_hist, name=f"{ch_name} after",
                                  line=dict(color=color, width=2)),
                       row=1, col=i+1)

    fig2.update_layout(
        height=280,
        margin=dict(l=40, r=20, t=50, b=40),
        template="plotly_dark",
        showlegend=False,
    )
    st.plotly_chart(fig2, width='stretch')

    # ─── Tone curve visualization ─────────────────────────────────────────────

    st.markdown("#### Tone Curve (Input → Output)")

    ev = params["ev"]
    gamma = params["gamma"]
    contrast = params["contrast_amount"]
    s_curve = params["s_curve"]
    bp = params["black_point"]
    wp = params["white_point"]

    x = np.linspace(0, 255, 256)
    y = x.copy().astype(np.float64)

    # Exposure
    y = y * (2.0 ** ev)
    # Gamma
    y = np.clip(y / 255.0, 0, 1) ** (1.0 / gamma) * 255.0
    # Black/white point
    if bp > 0:
        y = np.where(y < bp, 0, (y - bp) * 255.0 / (255 - bp))
    if wp < 255:
        y = np.where(y > wp, 255, y * 255.0 / wp)
    # Linear contrast
    if contrast != 0:
        factor = 1.0 + contrast / 100.0
        y = 128.0 + (y - 128.0) * factor
    # S-curve
    if s_curve > 0:
        strength = s_curve / 100.0
        norm = np.clip(y / 255.0, 0, 1)
        k = 5.0 * strength
        sigmoid = 1.0 / (1.0 + np.exp(-k * (norm - 0.5)))
        y = (norm * (1 - strength) + sigmoid * strength) * 255.0

    y = np.clip(y, 0, 255)

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=x, y=x, name="Identity",
                              line=dict(color="gray", width=1, dash="dot")))
    fig3.add_trace(go.Scatter(x=x, y=y, name="Curve",
                              line=dict(color="#00d4aa", width=2.5)))
    fig3.update_layout(
        xaxis_title="Input", yaxis_title="Output",
        height=300,
        margin=dict(l=40, r=20, t=30, b=40),
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig3, width='stretch')

else:
    st.info("👆 Upload an image to start. Adjust the sliders in the sidebar to see live changes.")


# ─── Batch Process Section ───────────────────────────────────────────────────

st.markdown("---")
st.markdown("### 📁 Batch Process Directory")

batch_col1, batch_col2 = st.columns([2, 1])
with batch_col1:
    batch_input = st.text_input("Input directory", value="", placeholder="/path/to/images")
with batch_col2:
    batch_output = st.text_input("Output directory", value="", placeholder="/path/to/output")

if st.button("Process All") and batch_input and batch_output:
    input_dir = Path(batch_input)
    output_dir = Path(batch_output)

    if not input_dir.exists():
        st.error(f"Input directory not found: {input_dir}")
    else:
        overrides = {
            "exposure.ev": st.session_state.ev,
            "exposure.gamma": st.session_state.gamma,
            "exposure.highlights": st.session_state.highlights,
            "exposure.shadows": st.session_state.shadows,
            "contrast.amount": st.session_state.contrast_amount,
            "contrast.s_curve": st.session_state.s_curve,
            "contrast.black_point": st.session_state.black_point,
            "contrast.white_point": st.session_state.white_point,
            "white_balance.temperature": st.session_state.temperature,
            "white_balance.tint": st.session_state.tint,
            "saturation.amount": st.session_state.saturation,
            "saturation.vibrance": st.session_state.vibrance,
            "lut.path": st.session_state.lut_path if st.session_state.lut_path != "None" else None,
            "lut.intensity": st.session_state.lut_intensity,
            "output.format": st.session_state.output_format,
            "output.quality": st.session_state.output_quality,
            "output.width": st.session_state.output_width if st.session_state.output_width > 0 else None,
        }

        from pipeline.processor import Pipeline
        pipe = Pipeline.from_profile(None, overrides)

        files = sorted([
            f for f in input_dir.iterdir()
            if f.suffix.lower() in (".tiff", ".tif", ".jpg", ".jpeg", ".png", ".webp")
            and f.is_file()
        ])

        if not files:
            st.warning(f"No images found in {input_dir}")
        else:
            progress = st.progress(0, text=f"Processing {len(files)} images...")
            results = []
            for i, f in enumerate(files):
                try:
                    out = pipe.process_image(f, output_dir)
                    if out:
                        results.append(out)
                        status_text = f"✅ {f.name}"
                    else:
                        status_text = f"❌ {f.name}"
                except Exception as e:
                    status_text = f"❌ {f.name}: {e}"
                progress.progress((i + 1) / len(files), text=f"[{i+1}/{len(files)}] {status_text}")

            st.success(f"✅ Done: {len(results)}/{len(files)} images processed → {output_dir}")