"""GPU-accelerated image operations using PyTorch MPS backend.

Optimized for Apple M1 Ultra with 128GB unified memory and 32-core GPU.
All operations work on torch tensors (H, W, 3) in float32, range 0-255.
"""

from __future__ import annotations

import functools
import pathlib
from typing import Optional

import numpy as np
import torch

# ─── Device setup ────────────────────────────────────────────────────────────

def get_device() -> torch.device:
    """Get the best available device: MPS (Apple Silicon) > CUDA > CPU."""
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


DEVICE = get_device()

# ─── Conversion helpers ──────────────────────────────────────────────────────

def numpy_to_torch(arr: np.ndarray) -> torch.Tensor:
    """Convert numpy (H, W, 3) float32 to torch tensor on device."""
    # arr is (H, W, 3) → torch wants (3, H, W) for most ops, but we keep (H, W, 3)
    # for elementwise ops. For grid_sample we'll permute.
    t = torch.from_numpy(arr).to(DEVICE)
    return t


def torch_to_numpy(t: torch.Tensor) -> np.ndarray:
    """Convert torch tensor back to numpy (H, W, 3) float32."""
    return t.detach().cpu().numpy().astype(np.float32)


# ─── LUT caching ─────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=32)
def _parse_cube_cached(path_str: str) -> dict:
    """Parse .cube LUT file with caching. Path must be string for lru_cache."""
    path = pathlib.Path(path_str)
    lut_type = None
    size = None
    domain_min = np.array([0.0, 0.0, 0.0])
    domain_max = np.array([1.0, 1.0, 1.0])
    rows = []

    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            upper = line.upper()
            if upper.startswith("LUT_1D_SIZE"):
                lut_type = "1D"
                size = int(line.split()[1])
                continue
            if upper.startswith("LUT_3D_SIZE"):
                lut_type = "3D"
                size = int(line.split()[1])
                continue
            if upper.startswith("DOMAIN_MIN"):
                vals = line.split()[1:4]
                domain_min = np.array([float(v) for v in vals])
                continue
            if upper.startswith("DOMAIN_MAX"):
                vals = line.split()[1:4]
                domain_max = np.array([float(v) for v in vals])
                continue
            if upper.startswith("TITLE"):
                continue
            parts = line.split()
            if len(parts) >= 3:
                rows.append([float(parts[0]), float(parts[1]), float(parts[2])])

    table = np.array(rows, dtype=np.float32)
    if lut_type == "1D":
        table = table.reshape(size, 3)
    elif lut_type == "3D":
        table = table.reshape(size, size, size, 3)

    return {
        "type": lut_type,
        "size": size,
        "table": table,
        "domain_min": domain_min,
        "domain_max": domain_max,
    }


@functools.lru_cache(maxsize=16)
def _get_lut_tensor(path_str: str) -> torch.Tensor:
    """Get LUT as a GPU tensor, cached. For 3D LUT returns (3, S, S, S) tensor."""
    lut = _parse_cube_cached(path_str)
    if lut["type"] == "3D":
        # (S, S, S, 3) → permute to (3, S, S, S) for grid_sample
        table = lut["table"].astype(np.float32)  # ensure float32 for MPS
        t = torch.from_numpy(table).permute(3, 0, 1, 2).to(DEVICE)
        return t
    else:
        # 1D LUT: (S, 3) → keep as is
        table = lut["table"].astype(np.float32)
        t = torch.from_numpy(table).to(DEVICE)
        return t


# ─── GPU Operations ──────────────────────────────────────────────────────────

def gpu_exposure(
    t: torch.Tensor,
    ev: float = 0.0,
    gamma: float = 1.0,
    highlights: int = 0,
    shadows: int = 0,
) -> torch.Tensor:
    """Exposure, gamma, highlight/shadow recovery on GPU."""
    result = t.clone()

    if ev != 0.0:
        result = result * (2.0 ** ev)

    if gamma != 1.0:
        normalized = result / 255.0
        normalized = normalized.clamp(0, 1) ** (1.0 / gamma)
        result = normalized * 255.0

    if highlights > 0:
        h_factor = highlights / 100.0
        normalized = result / 255.0
        mask = ((normalized - 0.5) * 2).clamp(0, 1)
        result = normalized * (1 - mask * h_factor * 0.5) * 255.0
    elif highlights < 0:
        h_factor = abs(highlights) / 100.0
        normalized = result / 255.0
        mask = ((normalized - 0.5) * 2).clamp(0, 1)
        result = (normalized + mask * h_factor * 0.3).clamp(0, 1) * 255.0

    if shadows > 0:
        s_factor = shadows / 100.0
        normalized = result / 255.0
        mask = ((0.5 - normalized) * 2).clamp(0, 1)
        result = (normalized + mask * s_factor * 0.3).clamp(0, 1) * 255.0
    elif shadows < 0:
        s_factor = abs(shadows) / 100.0
        normalized = result / 255.0
        mask = ((0.5 - normalized) * 2).clamp(0, 1)
        result = normalized * (1 - mask * s_factor * 0.5) * 255.0

    return result.clamp(0, 255)


def gpu_contrast(
    t: torch.Tensor,
    amount: int = 0,
    s_curve: int = 0,
    black_point: int = 0,
    white_point: int = 255,
) -> torch.Tensor:
    """Contrast adjustments on GPU."""
    result = t.clone()

    if black_point > 0:
        result = torch.where(
            result < black_point,
            torch.zeros_like(result),
            (result - black_point) * 255.0 / (255 - black_point),
        )
    if white_point < 255:
        result = torch.where(
            result > white_point,
            torch.full_like(result, 255.0),
            result * 255.0 / white_point,
        )

    if amount != 0:
        factor = 1.0 + amount / 100.0
        result = 128.0 + (result - 128.0) * factor

    if s_curve > 0:
        strength = s_curve / 100.0
        normalized = (result / 255.0).clamp(0, 1)
        k = 5.0 * strength
        sigmoid = 1.0 / (1.0 + torch.exp(-k * (normalized - 0.5)))
        result = (normalized * (1 - strength) + sigmoid * strength) * 255.0

    return result.clamp(0, 255)


def gpu_white_balance(
    t: torch.Tensor,
    temperature: int = 0,
    tint: int = 0,
) -> torch.Tensor:
    """White balance on GPU."""
    result = t.clone()

    if temperature != 0:
        t_val = temperature / 100.0
        r_gain = 1.0 + t_val * 0.15
        b_gain = 1.0 - t_val * 0.15
        result[..., 0] *= r_gain
        result[..., 2] *= b_gain

    if tint != 0:
        t_val = tint / 100.0
        g_gain = 1.0 - t_val * 0.12
        rb_gain = 1.0 + t_val * 0.06
        result[..., 0] *= rb_gain
        result[..., 1] *= g_gain
        result[..., 2] *= rb_gain

    return result.clamp(0, 255)


def gpu_saturation(
    t: torch.Tensor,
    amount: int = 0,
    vibrance: int = 0,
) -> torch.Tensor:
    """Saturation and vibrance on GPU using vectorized HSL."""
    if amount == 0 and vibrance == 0:
        return t

    rgb = t / 255.0
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]

    maxc = rgb.max(dim=-1).values
    minc = rgb.min(dim=-1).values
    delta = maxc - minc

    l = (maxc + minc) / 2.0

    # Saturation
    s = torch.where(
        delta == 0,
        torch.zeros_like(delta),
        torch.where(
            l < 0.5,
            delta / (maxc + minc + 1e-10),
            delta / (2.0 - maxc - minc + 1e-10),
        ),
    )

    # Hue (0-360)
    rc = torch.where(delta == 0, torch.zeros_like(delta), (maxc - r) / (delta + 1e-10))
    gc = torch.where(delta == 0, torch.zeros_like(delta), (maxc - g) / (delta + 1e-10))
    bc = torch.where(delta == 0, torch.zeros_like(delta), (maxc - b) / (delta + 1e-10))

    h = torch.where(maxc == r, bc - gc, torch.where(maxc == g, 2.0 + rc - bc, 4.0 + gc - rc))
    h = (h / 6.0) % 1.0
    h = h * 360.0

    # Global saturation
    if amount != 0:
        s = (s * (1.0 + amount / 100.0)).clamp(0, 1)

    # Vibrance
    if vibrance != 0:
        v = vibrance / 100.0
        weight = 1.0 - s * 0.8
        s = (s + v * weight * 0.6).clamp(0, 1)
        # Protect skin tones
        skin_mask = ((h > 10) & (h < 50)).float()
        s = s * (1.0 - skin_mask * abs(v) * 0.3)

    # HSL → RGB
    h_norm = h / 360.0
    c = (1.0 - (2.0 * l - 1.0).abs()) * s
    x = c * (1.0 - ((h_norm * 6.0) % 2.0 - 1.0).abs())
    m = l - c / 2.0

    sector = (h_norm * 6.0).long() % 6

    r_out = torch.zeros_like(l)
    g_out = torch.zeros_like(l)
    b_out = torch.zeros_like(l)

    masks = [sector == i for i in range(6)]
    r_vals = [c, x, torch.zeros_like(c), torch.zeros_like(c), x, c]
    g_vals = [x, c, c, x, torch.zeros_like(c), torch.zeros_like(c)]
    b_vals = [torch.zeros_like(c), torch.zeros_like(c), x, c, c, x]

    for i in range(6):
        r_out = r_out + masks[i] * r_vals[i]
        g_out = g_out + masks[i] * g_vals[i]
        b_out = b_out + masks[i] * b_vals[i]

    result = torch.stack([r_out + m, g_out + m, b_out + m], dim=-1) * 255.0
    return result.clamp(0, 255)


def gpu_lut(
    t: torch.Tensor,
    lut_path: Optional[str],
    intensity: float = 1.0,
) -> torch.Tensor:
    """Apply 3D LUT on GPU using grid_sample for fast trilinear interpolation."""
    if lut_path is None:
        return t

    lut = _parse_cube_cached(lut_path)

    if lut["type"] == "1D":
        return _gpu_1d_lut(t, lut, intensity)
    else:
        return _gpu_3d_lut(t, lut, intensity, lut_path)


def _gpu_3d_lut(t: torch.Tensor, lut: dict, intensity: float, lut_path: str = "") -> torch.Tensor:
    """3D LUT via grid_sample — extremely fast on GPU."""
    size = lut["size"]
    # Convert to float32 explicitly (MPS doesn't support float64)
    dmin = torch.from_numpy(lut["domain_min"].astype(np.float32)).to(DEVICE)
    dmax = torch.from_numpy(lut["domain_max"].astype(np.float32)).to(DEVICE)

    # Get LUT tensor (3, S, S, S) — already float32 from numpy table
    lut_tensor = _get_lut_tensor(lut_path)

    # Normalize image to 0-1, then to LUT domain
    normalized = t / 255.0
    normalized = normalized.clamp(dmin[0], dmax[0])

    # Map to -1..1 for grid_sample (normalized coordinates)
    domain_range = dmax - dmin
    idx = (normalized - dmin) / domain_range  # 0..1

    # grid_sample expects grid in [-1, 1] and (N, C_out, D, H, W) for 3D
    # For 3D LUT we use grid_sample with 3D volumes

    # Reshape: (H, W, 3) → (1, 3, H, W) then we need 3D grid_sample
    # Actually for 3D LUT, we treat it as volume sampling
    H, W = t.shape[0], t.shape[1]

    # LUT tensor: (3, S, S, S) → (1, 3, S, S, S) for grid_sample 3D
    lut_5d = lut_tensor.unsqueeze(0)  # (1, 3, S, S, S)

    # Create grid: (1, H, W, 1, 3) — order is (x, y, z) = (R, G, B) mapped to (-1, 1)
    # For 3D grid_sample, grid shape is (N, D_out, H_out, W_out, 3)
    # We want D_out=1, H_out=H, W_out=W

    r_norm = idx[..., 0] * 2 - 1  # -1..1
    g_norm = idx[..., 1] * 2 - 1
    b_norm = idx[..., 2] * 2 - 1

    # grid_sample 3D: grid coordinates are (x, y, z) which map to (W, H, D) dims
    # LUT is (3, S_R, S_G, S_B) → dims are (D=S_R, H=S_G, W=S_B)
    # grid order: (x=S_B, y=S_G, z=S_R) → need (b_norm, g_norm, r_norm)
    grid = torch.stack([b_norm, g_norm, r_norm], dim=-1)  # (H, W, 3)
    grid = grid.unsqueeze(0).unsqueeze(2)  # (1, 1, H, W, 3)

    # grid_sample 3D: input (N, C, D, H, W), grid (N, D_out, H_out, W_out, 3)
    sampled = torch.nn.functional.grid_sample(
        lut_5d, grid, mode='bilinear', padding_mode='border', align_corners=True
    )  # (1, 3, 1, H, W)

    result = sampled.squeeze(0).squeeze(2).permute(1, 2, 0)  # (H, W, 3)
    result = result * 255.0

    if intensity < 1.0:
        result = t * (1.0 - intensity) + result * intensity

    return result.clamp(0, 255)


def _gpu_1d_lut(t: torch.Tensor, lut: dict, intensity: float) -> torch.Tensor:
    """1D LUT via simple indexing on GPU."""
    size = lut["size"]
    table = torch.from_numpy(lut["table"].astype(np.float32)).to(DEVICE)  # (S, 3)
    dmin = torch.from_numpy(lut["domain_min"].astype(np.float32)).to(DEVICE)
    dmax = torch.from_numpy(lut["domain_max"].astype(np.float32)).to(DEVICE)

    normalized = (t / 255.0).clamp(dmin[0], dmax[0])
    idx = ((normalized - dmin) / (dmax - dmin) * (size - 1)).long().clamp(0, size - 1)

    result = torch.stack([
        table[idx[..., 0], 0],
        table[idx[..., 1], 1],
        table[idx[..., 2], 2],
    ], dim=-1) * 255.0

    if intensity < 1.0:
        result = t * (1.0 - intensity) + result * intensity

    return result.clamp(0, 255)


# Helper for lru_cache key
_lut_path_map = {}

def lut_path_str(lut: dict) -> str:
    """Get a string key for a parsed LUT for tensor caching."""
    # This is a fallback; in practice we cache by file path directly
    return str(id(lut))


# ─── Full GPU pipeline ───────────────────────────────────────────────────────

def gpu_process(
    arr: np.ndarray,
    params: dict,
) -> np.ndarray:
    """Run full processing pipeline on GPU.

    Args:
        arr: numpy (H, W, 3) float32, 0-255
        params: dict with ev, gamma, highlights, shadows, contrast_amount,
                s_curve, black_point, white_point, temperature, tint,
                saturation, vibrance, lut_path, lut_intensity

    Returns:
        numpy (H, W, 3) float32, 0-255
    """
    t = numpy_to_torch(arr)

    t = gpu_exposure(
        t, ev=params["ev"], gamma=params["gamma"],
        highlights=params["highlights"], shadows=params["shadows"],
    )
    t = gpu_contrast(
        t, amount=params["contrast_amount"], s_curve=params["s_curve"],
        black_point=params["black_point"], white_point=params["white_point"],
    )
    t = gpu_white_balance(
        t, temperature=params["temperature"], tint=params["tint"],
    )
    t = gpu_saturation(
        t, amount=params["saturation"], vibrance=params["vibrance"],
    )
    t = gpu_lut(
        t, lut_path=params.get("lut_path"), intensity=params.get("lut_intensity", 1.0),
    )

    return torch_to_numpy(t)


def gpu_process_from_pil(
    img,
    params: dict,
) -> "Image":
    """Convenience: PIL → GPU process → PIL."""
    from PIL import Image
    if img.mode != "RGB":
        img = img.convert("RGB")
    arr = np.array(img, dtype=np.float32)
    result = gpu_process(arr, params)
    return Image.fromarray(np.clip(result, 0, 255).astype(np.uint8), "RGB")