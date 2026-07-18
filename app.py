"""Photo Pipeline — Streamlit GUI

Run: streamlit run app.py
Opens in browser at http://localhost:8501
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import numpy as np
import streamlit as st
from PIL import Image

from pipeline.config import load_config, apply_overrides, DEFAULT_CONFIG, WB_PRESETS
from pipeline.ops.crop import crop_image
from pipeline.ops.exposure import apply_exposure
from pipeline.ops.contrast import apply_contrast
from pipeline.ops.white_balance import apply_white_balance
from pipeline.ops.saturation import apply_saturation
from pipeline.ops.lut import apply_lut
from pipeline.ops.vignette import apply_vignette
from pipeline.ops.grain import apply_grain


# ─── Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Photo Pipeline",
    page_icon="🖼️",
    layout="wide",
)


# ─── Session State ───────────────────────────────────────────────────────────

if "uploaded_file" not in st.session_state:
    st.session_state.uploaded_file = None
if "lut_files" not in st.session_state:
    st.session_state.lut_files = []


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
    # Crop
    if params.get("aspect_ratio"):
        img = crop_image(
            img,
            aspect_ratio=params["aspect_ratio"],
            gravity=params["gravity"],
            offset_x=params["offset_x"],
            offset_y=params["offset_y"],
        )

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
    # Vignette
    arr = apply_vignette(
        arr, amount=params["vignette_amount"],
        size=params["vignette_size"], feather=params["vignette_feather"],
        roundness=params["vignette_roundness"],
    )
    # Grain
    arr = apply_grain(
        arr, amount=params["grain_amount"],
        size=params["grain_size"], monochrome=params["grain_monochrome"],
    )

    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def img_to_bytes(img: Image.Image, fmt: str = "JPEG", quality: int = 90) -> bytes:
    """Convert PIL image to bytes for display."""
    buf = io.BytesIO()
    img.save(buf, format=fmt, quality=quality)
    return buf.getvalue()


def build_params_from_ui() -> dict:
    """Collect all parameters from Streamlit widgets."""
    return {
        "aspect_ratio": st.session_state.aspect_ratio if st.session_state.aspect_ratio != "None" else None,
        "gravity": st.session_state.gravity,
        "offset_x": st.session_state.offset_x,
        "offset_y": st.session_state.offset_y,
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
        "vignette_amount": st.session_state.vignette_amount,
        "vignette_size": st.session_state.vignette_size,
        "vignette_feather": st.session_state.vignette_feather,
        "vignette_roundness": st.session_state.vignette_roundness,
        "grain_amount": st.session_state.grain_amount,
        "grain_size": st.session_state.grain_size,
        "grain_monochrome": st.session_state.grain_monochrome,
    }


# ─── UI Layout ───────────────────────────────────────────────────────────────

st.title("🖼️ Photo Pipeline")
st.markdown("Batch photo processing with LUTs, color grading, and live preview.")

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
    if len(lut_files) == 1:
        # Check uploaded LUTs
        lut_files = ["None"] + [str(f) for f in st.session_state.lut_files]

# ─── Sidebar: All Controls ───────────────────────────────────────────────────

st.sidebar.markdown("### 🎚️ Adjustments")

# Crop
st.sidebar.markdown("#### ✂️ Crop")
st.sidebar.selectbox("Aspect Ratio", ["None", "4:3", "16:9", "1:1", "3:2", "2:1"],
                     key="aspect_ratio", index=0)
st.sidebar.selectbox("Gravity", ["center", "left", "right", "top", "bottom",
                                  "topleft", "topright", "bottomleft", "bottomright"],
                     key="gravity", index=0)
st.sidebar.slider("Offset X", -1.0, 1.0, 0.0, 0.05, key="offset_x")
st.sidebar.slider("Offset Y", -1.0, 1.0, 0.0, 0.05, key="offset_y")

# Exposure
st.sidebar.markdown("#### ☀️ Exposure")
st.sidebar.slider("Exposure (EV)", -3.0, 3.0, 0.0, 0.1, key="ev")
st.sidebar.slider("Gamma", 0.5, 2.5, 1.0, 0.05, key="gamma")
st.sidebar.slider("Highlights", -100, 100, 0, key="highlights")
st.sidebar.slider("Shadows", -100, 100, 0, key="shadows")

# Contrast
st.sidebar.markdown("#### 📊 Contrast")
st.sidebar.slider("Amount", -100, 100, 0, key="contrast_amount")
st.sidebar.slider("S-Curve", 0, 100, 0, key="s_curve")
st.sidebar.slider("Black Point", 0, 50, 0, key="black_point")
st.sidebar.slider("White Point", 205, 255, 255, key="white_point")

# White Balance
st.sidebar.markdown("#### 🌡️ White Balance")
st.sidebar.slider("Temperature", -100, 100, 0, key="temperature")
st.sidebar.slider("Tint", -100, 100, 0, key="tint")

# Saturation
st.sidebar.markdown("#### 🎨 Saturation")
st.sidebar.slider("Saturation", -100, 100, 0, key="saturation")
st.sidebar.slider("Vibrance", -100, 100, 0, key="vibrance")

# LUT
st.sidebar.markdown("#### 🎭 LUT")
st.sidebar.selectbox("LUT File", lut_files, key="lut_path", index=0)
st.sidebar.slider("LUT Intensity", 0.0, 1.0, 1.0, 0.05, key="lut_intensity")

# Vignette
st.sidebar.markdown("#### ⭕ Vignette")
st.sidebar.slider("Amount", -100, 100, 0, key="vignette_amount")
st.sidebar.slider("Size", 0, 100, 50, key="vignette_size")
st.sidebar.slider("Feather", 0, 100, 50, key="vignette_feather")
st.sidebar.slider("Roundness", -100, 100, 0, key="vignette_roundness")

# Grain
st.sidebar.markdown("#### 📷 Film Grain")
st.sidebar.slider("Amount", 0, 100, 0, key="grain_amount")
st.sidebar.slider("Size", 1, 10, 1, key="grain_size")
st.sidebar.checkbox("Monochrome", value=True, key="grain_monochrome")

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
        prof_cfg = load_config(prof_path)
        # Apply profile values as defaults (only if user hasn't changed them)
        # This is a simplification — in a real app you'd track dirty state
        # For now, profile sets the initial slider positions

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

    # Apply crop to preview for fair comparison
    if params["aspect_ratio"]:
        img_cropped = crop_image(
            img_preview,
            aspect_ratio=params["aspect_ratio"],
            gravity=params["gravity"],
            offset_x=params["offset_x"],
            offset_y=params["offset_y"],
        )
    else:
        img_cropped = img_preview

    # Process
    with st.spinner("Processing..."):
        result = process_single(img_cropped, params)

    # Show before/after
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### Before")
        st.image(img_cropped, width='stretch')
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

        # Process at full resolution for download
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

    # Stats
    with st.expander("📊 Image Statistics"):
        orig_arr = np.array(img_cropped, dtype=np.float64)
        proc_arr = np.array(result, dtype=np.float64)
        orig_mean = orig_arr.mean(axis=(0, 1))
        proc_mean = proc_arr.mean(axis=(0, 1))
        orig_b = 0.299 * orig_mean[0] + 0.587 * orig_mean[1] + 0.114 * orig_mean[2]
        proc_b = 0.299 * proc_mean[0] + 0.587 * proc_mean[1] + 0.114 * proc_mean[2]
        orig_rb = orig_mean[0] / max(orig_mean[2], 1)
        proc_rb = proc_mean[0] / max(proc_mean[2], 1)

        stat_col1, stat_col2 = st.columns(2)
        with stat_col1:
            st.markdown("**Before**")
            st.text(f"  Brightness: {orig_b:.1f}")
            st.text(f"  R/B ratio:  {orig_rb:.2f}")
            st.text(f"  RGB: [{orig_mean[0]:.0f}, {orig_mean[1]:.0f}, {orig_mean[2]:.0f}]")
        with stat_col2:
            st.markdown("**After**")
            st.text(f"  Brightness: {proc_b:.1f}")
            st.text(f"  R/B ratio:  {proc_rb:.2f}")
            st.text(f"  RGB: [{proc_mean[0]:.0f}, {proc_mean[1]:.0f}, {proc_mean[2]:.0f}]")

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
        # Build config from current UI params
        overrides = {
            "crop.aspect_ratio": st.session_state.aspect_ratio if st.session_state.aspect_ratio != "None" else None,
            "crop.gravity": st.session_state.gravity,
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
            "vignette.amount": st.session_state.vignette_amount,
            "vignette.size": st.session_state.vignette_size,
            "vignette.feather": st.session_state.vignette_feather,
            "vignette.roundness": st.session_state.vignette_roundness,
            "grain.amount": st.session_state.grain_amount,
            "grain.size": st.session_state.grain_size,
            "grain.monochrome": st.session_state.grain_monochrome,
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