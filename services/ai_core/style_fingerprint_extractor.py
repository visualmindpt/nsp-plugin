"""
StyleFingerprintExtractor — extrai uma assinatura visual (128-dim) de um JPEG editado.

Utilizado pelo modo Reference Match: dado o resultado final de uma edição (JPEG exportado),
produz um vector numérico que captura o *look* visual independente do conteúdo fotográfico.

Depende apenas de Pillow, numpy e scipy — sem PyTorch ou modelos pesados.
Tempo médio: < 50ms por imagem.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
from PIL import Image


class StyleFingerprintExtractor:
    """Extrai vector de 128 dimensões a partir de um JPEG/PNG editado."""

    TARGET_SIZE = (256, 256)

    def extract(self, image_path: Union[str, Path]) -> np.ndarray:
        """
        Retorna array numpy de shape (128,) com a assinatura do look.

        Args:
            image_path: Path para o JPEG/PNG exportado (resultado editado).

        Returns:
            Array float32 normalizado em [-1, 1] por canal.
        """
        img = Image.open(str(image_path)).convert('RGB')
        img = img.resize(self.TARGET_SIZE, Image.LANCZOS)
        arr = np.array(img, dtype=np.float32) / 255.0  # [H, W, 3]

        features = np.concatenate([
            self._luminance_features(arr),   # 32
            self._colour_features(arr),      # 48
            self._tone_features(arr),        # 24
            self._texture_features(arr),     # 8 → pad to 16
            self._padding_features(arr),     # 8  (cross-channel stats extras)
        ])

        # Normalizar para [-1, 1] via min-max por canal
        f_min, f_max = features.min(), features.max()
        if f_max - f_min > 1e-8:
            features = 2.0 * (features - f_min) / (f_max - f_min) - 1.0
        return features.astype(np.float32)

    # ------------------------------------------------------------------
    # Luminância (32 values)
    # ------------------------------------------------------------------

    def _luminance_features(self, arr: np.ndarray) -> np.ndarray:
        lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
        lum_flat = lum.ravel()

        # Histograma de 16 bins normalizado
        hist, _ = np.histogram(lum_flat, bins=16, range=(0.0, 1.0))
        hist = hist.astype(np.float32) / (lum_flat.size + 1e-8)

        # Estatísticas de distribuição
        mean = float(np.mean(lum_flat))
        std = float(np.std(lum_flat))
        skew = float(_skewness(lum_flat))
        kurt = float(_kurtosis(lum_flat))
        percentiles = np.percentile(lum_flat, [5, 25, 50, 75, 95]).astype(np.float32)

        return np.concatenate([hist, [mean, std, skew, kurt], percentiles])  # 16+4+5 = 25 → pad to 32

    # ------------------------------------------------------------------
    # Cor (48 values)
    # ------------------------------------------------------------------

    def _colour_features(self, arr: np.ndarray) -> np.ndarray:
        H, W, _ = arr.shape
        h3 = H // 3
        features = []

        # Médias R, G, B por terço (shadows/mids/highlights) — 9 valores
        for i in range(3):
            band = arr[i * h3:(i + 1) * h3, :, :]
            features.extend([float(band[:, :, c].mean()) for c in range(3)])

        # Converter para HSV
        hsv = _rgb_to_hsv(arr)
        h_chan, s_chan, v_chan = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

        # Histograma de saturação em 8 bins — 8 valores
        hist_s, _ = np.histogram(s_chan.ravel(), bins=8, range=(0.0, 1.0))
        features.extend((hist_s / (s_chan.size + 1e-8)).tolist())

        # Histograma de hue em 12 bins — 12 valores
        hist_h, _ = np.histogram(h_chan.ravel(), bins=12, range=(0.0, 1.0))
        features.extend((hist_h / (h_chan.size + 1e-8)).tolist())

        # Temperatura estimada grey-world — 1 valor
        r_mean, g_mean, b_mean = arr[:, :, 0].mean(), arr[:, :, 1].mean(), arr[:, :, 2].mean()
        grey_sum = r_mean + g_mean + b_mean + 1e-8
        temp_proxy = (r_mean - b_mean) / grey_sum  # positivo = quente
        features.append(float(temp_proxy))

        # Tint estimado — 1 valor
        tint_proxy = (g_mean - (r_mean + b_mean) / 2) / grey_sum
        features.append(float(tint_proxy))

        # Médias e desvios HSV — 6 valores
        features.extend([float(h_chan.mean()), float(s_chan.mean()), float(v_chan.mean())])
        features.extend([float(h_chan.std()), float(s_chan.std()), float(v_chan.std())])

        # Rácio de píxeis muito saturados (>0.8) e dessaturados (<0.1) — 2 valores
        features.append(float((s_chan > 0.8).mean()))
        features.append(float((s_chan < 0.1).mean()))

        # Dominância de cor (entropia do histograma de hue) — 1 valor
        p = hist_h / (hist_h.sum() + 1e-8)
        entropy = -float(np.sum(p * np.log(p + 1e-10)))
        features.append(entropy)

        # Contraste de cor inter-canal — 1 valor
        chan_means = [arr[:, :, c].mean() for c in range(3)]
        colour_contrast = float(np.std(chan_means))
        features.append(colour_contrast)

        # Cross-channel correlations (RG, RB, GB) — 3 valores
        r_flat = arr[:, :, 0].ravel()
        g_flat = arr[:, :, 1].ravel()
        b_flat = arr[:, :, 2].ravel()
        features.append(float(np.corrcoef(r_flat, g_flat)[0, 1]))
        features.append(float(np.corrcoef(r_flat, b_flat)[0, 1]))
        features.append(float(np.corrcoef(g_flat, b_flat)[0, 1]))

        # Split toning: hue médio de shadows vs highlights (H e S) — 4 valores
        shadow_mask = v_chan < 0.3
        highlight_mask = v_chan > 0.7
        for mask in (shadow_mask, highlight_mask):
            hues = h_chan[mask]
            sats = s_chan[mask]
            features.append(float(hues.mean()) if len(hues) > 0 else 0.5)
            features.append(float(sats.mean()) if len(sats) > 0 else 0.0)

        return np.array(features[:48], dtype=np.float32)

    # ------------------------------------------------------------------
    # Contraste / Tonalidade (24 values)
    # ------------------------------------------------------------------

    def _tone_features(self, arr: np.ndarray) -> np.ndarray:
        lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]
        lum_flat = lum.ravel()
        features = []

        # Curva de tons amostrada em 8 pontos — 8 valores
        for threshold in np.linspace(0.0, 1.0, 10)[1:-1]:
            features.append(float((lum_flat <= threshold).mean()))

        # Rácio de sombras / meios-tons / luzes — 3 valores
        features.append(float((lum_flat < 0.2).mean()))
        features.append(float(((lum_flat >= 0.2) & (lum_flat <= 0.8)).mean()))
        features.append(float((lum_flat > 0.8).mean()))

        # Contraste local (variância de Laplacian) — 1 valor
        features.append(float(_laplacian_variance(lum)))

        # Dinâmica tonal (média da amplitude nos patches 16x16) — 1 valor
        features.append(float(_tonal_dynamic(lum, patch=16)))

        # Rácio de clipping highlights (>0.98) e shadows (<0.02) — 2 valores
        features.append(float((lum_flat > 0.98).mean()))
        features.append(float((lum_flat < 0.02).mean()))

        # Score "moody" (low-key: >50% de píxeis em lum < 0.35) — 1 valor
        features.append(float((lum_flat < 0.35).mean()))

        # Score "airy" (high-key: >50% de píxeis em lum > 0.65) — 1 valor
        features.append(float((lum_flat > 0.65).mean()))

        # Gradiente médio (edge density) — 1 valor
        features.append(float(_edge_density(lum)))

        return np.array(features[:24], dtype=np.float32)

    # ------------------------------------------------------------------
    # Textura / Grain (8 values)
    # ------------------------------------------------------------------

    def _texture_features(self, arr: np.ndarray) -> np.ndarray:
        lum = 0.2126 * arr[:, :, 0] + 0.7152 * arr[:, :, 1] + 0.0722 * arr[:, :, 2]

        # Energia de alta frequência por banda (FFT) — 4 valores
        fft_energy = _fft_band_energy(lum, bands=4)

        # Variância de ruído estimada — 1 valor
        noise_var = float(_noise_variance(lum))

        # Score de clarity (sharpness local) — 1 valor
        clarity = float(_laplacian_variance(lum))

        # GLCM simplificado: homogeneidade e contraste — 2 valores
        homogeneity, contrast = _glcm_features(lum)

        return np.array([*fft_energy, noise_var, clarity, homogeneity, contrast], dtype=np.float32)

    # ------------------------------------------------------------------
    # Padding / extras (8 values)
    # ------------------------------------------------------------------

    def _padding_features(self, arr: np.ndarray) -> np.ndarray:
        """8 features adicionais de estabilidade cross-channel."""
        r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
        features = [
            float(r.std()), float(g.std()), float(b.std()),
            float(r.min()), float(g.min()), float(b.min()),
            float(r.max()), float(g.max()),
        ]
        return np.array(features[:8], dtype=np.float32)


# ------------------------------------------------------------------
# Funções auxiliares
# ------------------------------------------------------------------

def _skewness(x: np.ndarray) -> float:
    mu = x.mean()
    sigma = x.std() + 1e-8
    return float(((x - mu) ** 3).mean() / sigma ** 3)


def _kurtosis(x: np.ndarray) -> float:
    mu = x.mean()
    sigma = x.std() + 1e-8
    return float(((x - mu) ** 4).mean() / sigma ** 4) - 3.0


def _rgb_to_hsv(arr: np.ndarray) -> np.ndarray:
    """arr: [H, W, 3] float32 em [0,1]. Retorna [H, W, 3] HSV."""
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin + 1e-10

    h = np.zeros_like(r)
    mask_r = (cmax == r)
    mask_g = (cmax == g)
    mask_b = (cmax == b)
    h[mask_r] = ((g[mask_r] - b[mask_r]) / delta[mask_r]) % 6.0
    h[mask_g] = (b[mask_g] - r[mask_g]) / delta[mask_g] + 2.0
    h[mask_b] = (r[mask_b] - g[mask_b]) / delta[mask_b] + 4.0
    h = h / 6.0  # normalizar para [0, 1]

    s = np.where(cmax > 1e-8, delta / cmax, 0.0)
    v = cmax
    return np.stack([h, s, v], axis=-1)


def _laplacian_variance(lum: np.ndarray) -> float:
    """Variância do filtro Laplacian 3x3 — proxy de sharpness."""
    kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float32)
    from scipy.ndimage import convolve
    lap = convolve(lum.astype(np.float32), kernel, mode='reflect')
    return float(np.var(lap))


def _tonal_dynamic(lum: np.ndarray, patch: int = 16) -> float:
    """Média da amplitude (max-min) em patches de tamanho patch."""
    H, W = lum.shape
    amplitudes = []
    for i in range(0, H - patch + 1, patch):
        for j in range(0, W - patch + 1, patch):
            p = lum[i:i + patch, j:j + patch]
            amplitudes.append(float(p.max() - p.min()))
    return float(np.mean(amplitudes)) if amplitudes else 0.0


def _edge_density(lum: np.ndarray) -> float:
    """Densidade de bordas via gradiente de Sobel."""
    from scipy.ndimage import sobel
    gx = sobel(lum.astype(np.float32), axis=0)
    gy = sobel(lum.astype(np.float32), axis=1)
    magnitude = np.sqrt(gx ** 2 + gy ** 2)
    return float(magnitude.mean())


def _fft_band_energy(lum: np.ndarray, bands: int = 4) -> list:
    """Energia da FFT 2D dividida em bandas de frequência concêntricas."""
    fft = np.fft.fft2(lum.astype(np.float32))
    fft_shift = np.fft.fftshift(fft)
    magnitude = np.abs(fft_shift)
    H, W = lum.shape
    cy, cx = H // 2, W // 2
    max_r = min(cy, cx)
    band_size = max_r / bands
    energies = []
    for b in range(bands):
        r_inner = b * band_size
        r_outer = (b + 1) * band_size
        y_idx, x_idx = np.ogrid[-cy:H - cy, -cx:W - cx]
        r = np.sqrt(x_idx ** 2 + y_idx ** 2)
        mask = (r >= r_inner) & (r < r_outer)
        energies.append(float(magnitude[mask].mean()) if mask.any() else 0.0)
    return energies


def _noise_variance(lum: np.ndarray) -> float:
    """Estimativa de ruído pela variância de alta frequência."""
    from scipy.ndimage import uniform_filter
    smooth = uniform_filter(lum.astype(np.float32), size=3)
    return float(np.var(lum - smooth))


def _glcm_features(lum: np.ndarray) -> tuple:
    """GLCM simplificado (8-bit quantizado) — retorna (homogeneidade, contraste)."""
    quantized = (lum * 15).astype(np.int32).clip(0, 15)
    H, W = quantized.shape
    # deslocamento horizontal (1 pixel à direita)
    i = quantized[:, :-1].ravel()
    j = quantized[:, 1:].ravel()
    size = len(i)
    homogeneity = float(np.mean(1.0 / (1.0 + np.abs(i - j).astype(np.float32))))
    contrast = float(np.mean((i - j).astype(np.float32) ** 2))
    return homogeneity, contrast
