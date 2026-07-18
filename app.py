"""Photo Pipeline — Streamlit GUI

Run: streamlit run app.py
Opens in browser at http://localhost:8501
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import streamlit as st
import yaml
from PIL import Image

from pipeline.config import load_config
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

PROFILES_DIR = Path("profiles")


# ─── Session State ───────────────────────────────────────────────────────────

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None

_init_defaults = {
    "ev": 0.0, "gamma": 1.0, "highlights": 0, "shadows": 0,
    "contrast_amount": 0, "s_curve": 0, "black_point": 0, "white_point": 255,
    "temperature": 0, "tint": 0, "saturation": 0, "vibrance": 0,
    "lut_intensity": 1.0, "lut_path": "None",
    "output_format": "jpeg", "output_quality": 90,
    "third_profile_select": "None",
}
for _k, _v in _init_defaults.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ─── Helpers ─────────────────────────────────────────────────────────────────

@st.cache_data(max_entries=1)
def load_image_bytes(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def process_single(img: Image.Image, params: dict) -> Image.Image:
    arr = np.array(img, dtype=np.float32)
    arr = apply_exposure(
        arr, ev=params["ev"], gamma=params["gamma"],
        highlights=params["highlights"], shadows=params["shadows"],
    )
    arr = apply_contrast(
        arr, amount=params["contrast_amount"],
        s_curve=params["s_curve"],
        black_point=params["black_point"],
        white_point=params["white_point"],
    )
    arr = apply_white_balance(arr, temperature=params["temperature"], tint=params["tint"])
    arr = apply_saturation(arr, amount=params["saturation"], vibrance=params["vibrance"])
    if params.get("lut_path"):
        arr = apply_lut(arr, params["lut_path"], params["lut_intensity"])
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def build_params_from_ui() -> dict:
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
    return path


def list_profiles() -> list[str]:
    if not PROFILES_DIR.exists():
        return []
    return sorted([f.name for f in PROFILES_DIR.glob("*.yaml")])


def apply_profile_to_state(profile_name: str):
    path = PROFILES_DIR / profile_name
    if not path.exists():
        return
    cfg = load_config(path)
    exp = cfg.get("exposure", {})
    con = cfg.get("contrast", {})
    wb = cfg.get("white_balance", {})
    sat = cfg.get("saturation", {})
    lut = cfg.get("lut", {})
    st.session_state.ev = exp.get("ev", 0.0)
    st.session_state.gamma = exp.get("gamma", 1.0)
    st.session_state.highlights = exp.get("highlights", 0)
    st.session_state.shadows = exp.get("shadows", 0)
    st.session_state.contrast_amount = con.get("amount", 0)
    st.session_state.s_curve = con.get("s_curve", 0)
    st.session_state.black_point = con.get("black_point", 0)
    st.session_state.white_point = con.get("white_point", 255)
    st.session_state.temperature = wb.get("temperature", 0)
    st.session_state.tint = wb.get("tint", 0)
    st.session_state.saturation = sat.get("amount", 0)
    st.session_state.vibrance = sat.get("vibrance", 0)
    lp = lut.get("path")
    st.session_state.lut_path = lp if lp else "None"
    st.session_state.lut_intensity = lut.get("intensity", 1.0)


lut_dir = Path("luts")
lut_files = ["None"] + [str(f) for f in lut_dir.glob("*.cube")] if lut_dir.exists() else ["None"]

profiles_list = list_profiles()


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR — management controls (flat, no sliders)
# ═════════════════════════════════════════════════════════════════════════════

sb = st.sidebar

# Image upload
sb.markdown("### 📁 Image")
uploaded = sb.file_uploader(
    "Upload image", type=["tiff", "tif", "jpg", "jpeg", "png", "webp"],
    label_visibility="collapsed",
)
if uploaded:
    st.session_state.uploaded_file = uploaded.getvalue()

# 3rd Preview
sb.markdown("### 🖼️ 3rd Preview")
preview_options = ["None"] + profiles_list
third_choice = sb.selectbox("Select", preview_options,
                            key="third_profile_select", index=0, label_visibility="collapsed")
third_profile = third_choice if third_choice != "None" else None

# Profiles
sb.markdown("### 📋 Profiles")
if profiles_list:
    load_choice = sb.selectbox("YAML → Sliders", profiles_list,
                               key="load_profile_select", index=0)
    if sb.button("⬆️ Apply", key="apply_profile_btn", use_container_width=True):
        apply_profile_to_state(load_choice)
        st.rerun()
else:
    sb.caption("No profiles yet.")

save_name = sb.text_input("Sliders → YAML", placeholder="profile name",
                          key="save_profile_name")
if sb.button("💾 Save", key="save_profile_btn", use_container_width=True):
    if save_name.strip():
        params = build_params_from_ui()
        output_cfg = {
            "format": st.session_state.output_format,
            "quality": st.session_state.output_quality,
        }
        saved_path = save_profile(save_name.strip(), params, output_cfg)
        sb.success(f"Saved: `{saved_path.name}`")
        st.rerun()
    else:
        sb.error("Enter a name")

if profiles_list:
    del_choice = sb.selectbox("Delete", profiles_list,
                              key="del_profile_select", index=0)
    if sb.button("🗑️ Delete", key="del_profile_btn", use_container_width=True):
        (PROFILES_DIR / del_choice).unlink()
        st.rerun()

# Output
sb.markdown("### 💾 Output")
sb.selectbox("Format", ["jpeg", "webp", "avif", "tiff"],
             key="output_format", index=0, label_visibility="collapsed")
sb.slider("Quality", 1, 100, 90, key="output_quality")

# Download (only if image uploaded)
if st.session_state.uploaded_file:
    _img_dl = load_image_bytes(st.session_state.uploaded_file)
    _params_dl = build_params_from_ui()
    _fmt_dl = st.session_state.output_format
    _q_dl = st.session_state.output_quality
    _ext_dl = {"jpeg": "jpg", "webp": "webp", "avif": "avif", "tiff": "tiff"}[_fmt_dl]
    _pil_fmt_dl = {"jpeg": "JPEG", "webp": "WEBP", "avif": "AVIF", "tiff": "TIFF"}[_fmt_dl]
    _full_dl = process_single(_img_dl, _params_dl)
    _buf_dl = io.BytesIO()
    _kw_dl = {"quality": _q_dl} if _pil_fmt_dl in ("JPEG", "WEBP", "AVIF") else {}
    if _pil_fmt_dl == "JPEG":
        _kw_dl["subsampling"] = 0
    _full_dl.save(_buf_dl, format=_pil_fmt_dl, **_kw_dl)
    sb.download_button(
        f"⬇️ Download ({_ext_dl.upper()})",
        data=_buf_dl.getvalue(),
        file_name=f"processed.{_ext_dl}",
        mime=f"image/{_fmt_dl}",
    )

# Batch
sb.markdown("### 📁 Batch")
batch_input = sb.text_input("Input dir", value="", placeholder="/path/to/images",
                            key="batch_input")
batch_output = sb.text_input("Output dir", value="", placeholder="/path/to/output",
                             key="batch_output")
if sb.button("Process All", key="batch_process_btn", use_container_width=True):
    if batch_input and batch_output:
        st.session_state.batch_run = True
        st.session_state.batch_in = batch_input
        st.session_state.batch_out = batch_output
        st.rerun()
    else:
        sb.error("Enter both paths")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ═════════════════════════════════════════════════════════════════════════════

st.title("🖼️ Photo Pipeline")

# Batch result
if st.session_state.get("batch_run"):
    st.session_state.batch_run = False
    input_dir = Path(st.session_state.batch_in)
    output_dir = Path(st.session_state.batch_out)

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
    st.markdown("---")

if not st.session_state.uploaded_file:
    st.info("👆 Upload an image from the sidebar to start.")
    st.stop()


# ─── Process image ───────────────────────────────────────────────────────────

img = load_image_bytes(st.session_state.uploaded_file)
params = build_params_from_ui()

preview_w = 800
w, h = img.size
if w > preview_w:
    preview_h = int(h * preview_w / w)
    img_preview = img.resize((preview_w, preview_h), Image.LANCZOS)
else:
    img_preview = img

with st.spinner("Processing..."):
    result_live = process_single(img_preview, params)

result_profile = None
third_params = None
if third_profile:
    cfg_third = load_config(PROFILES_DIR / third_profile)
    third_params = params_from_config(cfg_third)
    result_profile = process_single(img_preview, third_params)


# ─── Preview ─────────────────────────────────────────────────────────────────

if result_profile is not None:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("#### Original")
        st.image(img_preview, width='stretch')
    with col2:
        st.markdown("#### Live Sliders")
        st.image(result_live, width='stretch')
    with col3:
        st.markdown(f"#### {third_profile}")
        st.image(result_profile, width='stretch')
else:
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Original")
        st.image(img_preview, width='stretch')
    with col2:
        st.markdown("#### After")
        st.image(result_live, width='stretch')


# ─── Adjustments (4 columns, below images) ───────────────────────────────────

st.markdown("---")
st.markdown("### 🎚️ Adjustments")

# Compact CSS for adjustment sliders
st.markdown("""
<style>
/* Compact adjustments section */
.adj-section .stSlider { margin-bottom: 0.25rem !important; }
.adj-section .stSlider > div { padding-top: 0.25rem !important; padding-bottom: 0.25rem !important; }
.adj-section .stSlider label { font-size: 0.8rem !important; margin-bottom: 0 !important; line-height: 1.2 !important; }
.adj-section .stMarkdown h4 { font-size: 0.9rem !important; margin-top: 0.3rem !important; margin-bottom: 0.2rem !important; }
.adj-section .stSelectbox { margin-bottom: 0.25rem !important; }
.adj-section .stSelectbox label { font-size: 0.8rem !important; }
</style>
""", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="adj-section">', unsafe_allow_html=True)

    adj_col1, adj_col2, adj_col3, adj_col4 = st.columns(4)

    with adj_col1:
        st.markdown("#### ☀️ Exposure")
        st.slider("EV", -3.0, 3.0, 0.0, 0.01, key="ev", format="%.2f")
        st.slider("Gamma", 0.5, 2.5, 1.0, 0.01, key="gamma", format="%.2f")
        st.slider("Highlights", -100, 100, 0, 1, key="highlights")
        st.slider("Shadows", -100, 100, 0, 1, key="shadows")

    with adj_col2:
        st.markdown("#### 📊 Contrast")
        st.slider("Amount", -100, 100, 0, 1, key="contrast_amount")
        st.slider("S-Curve", 0, 100, 0, 1, key="s_curve")
        st.slider("Black Point", 0, 50, 0, 1, key="black_point")
        st.slider("White Point", 205, 255, 255, 1, key="white_point")

    with adj_col3:
        st.markdown("#### 🌡️ White Balance")
        st.slider("Temperature", -100, 100, 0, 1, key="temperature")
        st.slider("Tint", -100, 100, 0, 1, key="tint")

        st.markdown("#### 🎨 Saturation")
        st.slider("Saturation", -100, 100, 0, 1, key="saturation")
        st.slider("Vibrance", -100, 100, 0, 1, key="vibrance")

    with adj_col4:
        st.markdown("#### 🎭 LUT")
        st.selectbox("LUT File", lut_files, key="lut_path", index=0, label_visibility="collapsed")
        st.slider("Intensity", 0.0, 1.0, 1.0, 0.01, key="lut_intensity", format="%.2f")

    st.markdown('</div>', unsafe_allow_html=True)


# ─── Statistics (collapsible, below adjustments) ─────────────────────────────

st.markdown("---")

orig_arr = np.array(img_preview, dtype=np.float64)
proc_arr = np.array(result_live, dtype=np.float64)


def channel_stats(arr):
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    return {
        "B_mean": lum.mean(), "B_med": np.median(lum), "B_std": lum.std(),
        "B_min": lum.min(), "B_max": lum.max(), "B_rng": lum.max() - lum.min(),
        "R": r.mean(), "G": g.mean(), "Bl": b.mean(),
        "R_sd": r.std(), "G_sd": g.std(), "Bl_sd": b.std(),
        "R/B": r.mean() / max(b.mean(), 1),
        "R/G": r.mean() / max(g.mean(), 1),
        "G/B": g.mean() / max(b.mean(), 1),
        "Sat": np.std(arr, axis=-1).mean(),
        "SNR": lum.mean() / max(lum.std(), 1),
        "Shd%": (lum < 50).sum() / lum.size * 100,
        "Mid%": ((lum >= 50) & (lum < 200)).sum() / lum.size * 100,
        "Hlt%": (lum >= 200).sum() / lum.size * 100,
        "Clip_S": (arr.min(axis=-1) < 3).sum() / arr.shape[0] / arr.shape[1] * 100,
        "Clip_H": (arr.max(axis=-1) > 252).sum() / arr.shape[0] / arr.shape[1] * 100,
    }


orig_stats = channel_stats(orig_arr)
proc_stats = channel_stats(proc_arr)
profile_stats = None
if result_profile is not None:
    profile_stats = channel_stats(np.array(result_profile, dtype=np.float64))

import pandas as pd
import plotly.graph_objects as go


with st.expander("📊 Statistics Table", expanded=False):
    data = {}
    for key in orig_stats:
        row = {"Original": orig_stats[key], "Live": proc_stats[key]}
        if profile_stats is not None:
            row["Profile"] = profile_stats[key]
        data[key] = row
    stats_df = pd.DataFrame(data).T.round(2)
    st.dataframe(stats_df, width='stretch')


with st.expander("📈 Histograms", expanded=False):
    def plot_histogram(arr, title):
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
            height=300, margin=dict(l=40, r=20, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_dark",
        )
        return fig

    if result_profile is not None:
        hc1, hc2, hc3 = st.columns(3)
        with hc1:
            st.plotly_chart(plot_histogram(orig_arr, "Original"), width='stretch')
        with hc2:
            st.plotly_chart(plot_histogram(proc_arr, "Live Sliders"), width='stretch')
        with hc3:
            st.plotly_chart(plot_histogram(np.array(result_profile, dtype=np.float64), third_profile), width='stretch')
    else:
        hc1, hc2 = st.columns(2)
        with hc1:
            st.plotly_chart(plot_histogram(orig_arr, "Before"), width='stretch')
        with hc2:
            st.plotly_chart(plot_histogram(proc_arr, "After"), width='stretch')


with st.expander("📊 Channel Deltas (After − Original)", expanded=False):
    bins = np.arange(0, 257, 1)
    channels = [("Red", "#ff4444", "rgba(255,68,68,0.2)"),
                ("Green", "#44ff44", "rgba(68,255,68,0.2)"),
                ("Blue", "#4488ff", "rgba(68,136,255,0.2)")]

    fig2 = go.Figure()
    for i, (ch_name, color, fillcolor) in enumerate(channels):
        orig_hist, _ = np.histogram(orig_arr[..., i], bins=bins)
        proc_hist, _ = np.histogram(proc_arr[..., i], bins=bins)
        delta = proc_hist.astype(np.float64) - orig_hist.astype(np.float64)
        fig2.add_trace(go.Scatter(
            x=bins[:-1], y=delta, name=ch_name,
            line=dict(color=color, width=2),
            fill="tozeroy", fillcolor=fillcolor,
        ))
    fig2.update_layout(
        title="Live − Original",
        xaxis_title="Value (0–255)", yaxis_title="Δ Pixel count",
        height=320, margin=dict(l=40, r=20, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_dark", hovermode="x unified", showlegend=True,
    )
    st.plotly_chart(fig2, width='stretch')

    if result_profile is not None:
        st.markdown("**Profile − Original:**")
        fig2b = go.Figure()
        for i, (ch_name, color, fillcolor) in enumerate(channels):
            orig_hist, _ = np.histogram(orig_arr[..., i], bins=bins)
            prof_hist, _ = np.histogram(np.array(result_profile, dtype=np.float64)[..., i], bins=bins)
            delta = prof_hist.astype(np.float64) - orig_hist.astype(np.float64)
            fig2b.add_trace(go.Scatter(
                x=bins[:-1], y=delta, name=ch_name,
                line=dict(color=color, width=2),
                fill="tozeroy", fillcolor=fillcolor,
            ))
        fig2b.update_layout(
            xaxis_title="Value (0–255)", yaxis_title="Δ Pixel count",
            height=320, margin=dict(l=40, r=20, t=30, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_dark", hovermode="x unified", showlegend=True,
        )
        st.plotly_chart(fig2b, width='stretch')


with st.expander("📈 Tone Curve (Input → Output)", expanded=False):
    def compute_curve(ev, gamma, contrast, s_curve, bp, wp):
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

    x, y_live = compute_curve(
        params["ev"], params["gamma"], params["contrast_amount"],
        params["s_curve"], params["black_point"], params["white_point"],
    )

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=x, y=x, name="Identity",
                              line=dict(color="gray", width=1, dash="dot")))
    fig3.add_trace(go.Scatter(x=x, y=y_live, name="Live Curve",
                              line=dict(color="#00d4aa", width=2.5)))
    if result_profile is not None:
        _, y_prof = compute_curve(
            third_params["ev"], third_params["gamma"], third_params["contrast_amount"],
            third_params["s_curve"], third_params["black_point"], third_params["white_point"],
        )
        fig3.add_trace(go.Scatter(x=x, y=y_prof, name="Profile Curve",
                                  line=dict(color="#ff9900", width=2, dash="dash")))
    fig3.update_layout(
        xaxis_title="Input", yaxis_title="Output", height=300,
        margin=dict(l=40, r=20, t=30, b=40), template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig3, width='stretch')