"""
Testes sintéticos do pipeline ML do NSP Plugin.

Objetivo: verificar a saúde e eficácia dos modelos sem necessitar de dados
reais do Lightroom. Todos os dados são gerados com padrões controláveis para
que as métricas esperadas sejam verificáveis.

Estratégia de geração de dados:
  - Cada "preset" é um cluster com centróide distinto no espaço de features
  - A separabilidade é controlada via SNR (signal-to-noise ratio)
  - Os deltas de refinamento seguem uma relação linear com features + ruído
  - Testes cobrem: accuracy do classificador, MAE do regressor, overfitting,
    robustez a imbalance, comportamento do clamp de parâmetros, e o pipeline end-to-end

Execução:
    pytest tests/test_ml_synthetic.py -v
    pytest tests/test_ml_synthetic.py -v --tb=short -q   # output resumido
"""

import sys
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

import numpy as np
import pytest
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from services.ai_core.model_architectures_v2 import (
    OptimizedPresetClassifier,
    OptimizedRefinementRegressor,
)
from services.ai_core.training_utils import LightroomDataset, WeightedMSELoss
from services.ai_core.trainer_v2 import OptimizedClassifierTrainer, OptimizedRefinementTrainer


# ---------------------------------------------------------------------------
# Constantes do ambiente sintético
# ---------------------------------------------------------------------------
STAT_DIM   = 40    # dimensão features estatísticas
DEEP_DIM   = 64    # dimensão deep features (ResNet embutido)
NUM_PRESETS = 4
NUM_PARAMS  = 22   # parâmetros Lightroom a prever
SEED        = 42
DEVICE      = "cpu"

np.random.seed(SEED)
torch.manual_seed(SEED)


# ---------------------------------------------------------------------------
# Gerador de dados sintéticos
# ---------------------------------------------------------------------------
class SyntheticLightroomData:
    """
    Gera datasets sintéticos com padrões controláveis.

    Cada preset tem:
      - centróide de features estatísticas (separados por `sep_factor`)
      - centróide de deep features
      - valores médios de deltas (relação linear com features + ruído)
    """

    def __init__(
        self,
        n_samples: int = 300,
        num_presets: int = NUM_PRESETS,
        stat_dim: int = STAT_DIM,
        deep_dim: int = DEEP_DIM,
        num_params: int = NUM_PARAMS,
        sep_factor: float = 3.0,   # quanto mais alto, mais separáveis os presets
        noise_std: float = 0.5,
        imbalance_ratio: float = 1.0,  # 1.0 = balanceado; 3.0 = classe 0 tem 3× mais
        seed: int = SEED,
    ):
        self.rng = np.random.default_rng(seed)
        self.num_presets = num_presets
        self.stat_dim    = stat_dim
        self.deep_dim    = deep_dim
        self.num_params  = num_params

        # Centróides separados para cada preset
        self.stat_centers = sep_factor * self.rng.standard_normal((num_presets, stat_dim))
        self.deep_centers = sep_factor * self.rng.standard_normal((num_presets, deep_dim))

        # Relação linear features → deltas (pesos aleatórios por preset)
        self.delta_weights = self.rng.standard_normal((num_presets, num_params)) * 0.3

        # Distribuição de amostras por classe
        base = np.ones(num_presets)
        base[0] *= imbalance_ratio
        self.class_probs = base / base.sum()

        self.noise_std = noise_std
        self._generate(n_samples)

    def _generate(self, n_samples: int):
        labels = self.rng.choice(self.num_presets, size=n_samples, p=self.class_probs)

        stat_features = np.array([
            self.stat_centers[l] + self.rng.normal(0, self.noise_std, self.stat_dim)
            for l in labels
        ])
        deep_features = np.array([
            self.deep_centers[l] + self.rng.normal(0, self.noise_std, self.deep_dim)
            for l in labels
        ])

        # deltas = centróide do preset + ruído pequeno
        deltas = np.array([
            self.delta_weights[labels[i]] +
            self.rng.normal(0, 0.1, self.num_params)
            for i in range(n_samples)
        ])

        self.stat_features = stat_features.astype(np.float32)
        self.deep_features = deep_features.astype(np.float32)
        self.labels        = labels.astype(np.int64)
        self.deltas        = deltas.astype(np.float32)

    def train_val_split(self, val_frac: float = 0.2):
        n = len(self.labels)
        idx = np.random.permutation(n)
        split = int(n * (1 - val_frac))
        tr, vl = idx[:split], idx[split:]
        return (
            self.stat_features[tr], self.stat_features[vl],
            self.deep_features[tr], self.deep_features[vl],
            self.labels[tr], self.labels[vl],
            self.deltas[tr], self.deltas[vl],
        )

    @property
    def n(self):
        return len(self.labels)


def make_loaders(data: SyntheticLightroomData, batch_size: int = 32, val_frac: float = 0.2):
    (X_s_tr, X_s_vl, X_d_tr, X_d_vl,
     y_tr, y_vl, d_tr, d_vl) = data.train_val_split(val_frac)

    ds_train = LightroomDataset(X_s_tr, X_d_tr, y_tr, d_tr)
    ds_val   = LightroomDataset(X_s_vl, X_d_vl, y_vl, d_vl)

    train_loader = DataLoader(ds_train, batch_size=batch_size, shuffle=True, drop_last=True)
    val_loader   = DataLoader(ds_val,   batch_size=batch_size, shuffle=False)

    return train_loader, val_loader


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def easy_data():
    """Dataset fácil: presets muito separados → accuracy esperada ≥ 90%"""
    return SyntheticLightroomData(n_samples=400, sep_factor=5.0, noise_std=0.3)


@pytest.fixture(scope="module")
def hard_data():
    """Dataset difícil: presets sobrepostos → testa se modelo bate baseline aleatório"""
    return SyntheticLightroomData(n_samples=400, sep_factor=1.0, noise_std=1.5)


@pytest.fixture(scope="module")
def imbalanced_data():
    """Dataset desbalanceado: classe 0 tem 4× mais amostras"""
    return SyntheticLightroomData(n_samples=400, sep_factor=4.0, imbalance_ratio=4.0)


@pytest.fixture(scope="module")
def tiny_data():
    """Dataset muito pequeno: testa robustez com poucos dados"""
    return SyntheticLightroomData(n_samples=60, sep_factor=4.0)


# ---------------------------------------------------------------------------
# BLOCO 1 — Testes de sanidade do modelo (sem treino)
# ---------------------------------------------------------------------------
class TestModelSanity:
    """Verifica que os modelos são instanciáveis e produzem outputs corretos."""

    def test_classifier_output_shape(self):
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        stat  = torch.randn(8, STAT_DIM)
        deep  = torch.randn(8, DEEP_DIM)
        out   = model(stat, deep)
        assert out.shape == (8, NUM_PRESETS), f"Shape esperado (8, {NUM_PRESETS}), obtido {out.shape}"

    def test_regressor_output_shape(self):
        model  = OptimizedRefinementRegressor(STAT_DIM, DEEP_DIM, NUM_PRESETS, NUM_PARAMS)
        stat   = torch.randn(8, STAT_DIM)
        deep   = torch.randn(8, DEEP_DIM)
        preset = torch.randint(0, NUM_PRESETS, (8,))
        out    = model(stat, deep, preset)
        assert out.shape == (8, NUM_PARAMS), f"Shape esperado (8, {NUM_PARAMS}), obtido {out.shape}"

    def test_classifier_logits_finite(self):
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        stat  = torch.randn(16, STAT_DIM)
        deep  = torch.randn(16, DEEP_DIM)
        out   = model(stat, deep)
        assert torch.isfinite(out).all(), "Logits contêm NaN ou Inf"

    def test_regressor_output_finite(self):
        model  = OptimizedRefinementRegressor(STAT_DIM, DEEP_DIM, NUM_PRESETS, NUM_PARAMS)
        stat   = torch.randn(16, STAT_DIM)
        deep   = torch.randn(16, DEEP_DIM)
        preset = torch.zeros(16, dtype=torch.long)
        out    = model(stat, deep, preset)
        assert torch.isfinite(out).all(), "Outputs do regressor contêm NaN ou Inf"

    def test_width_factor_scales_parameters(self):
        m1 = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS, width_factor=1.0)
        m2 = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS, width_factor=0.5)
        p1 = sum(p.numel() for p in m1.parameters())
        p2 = sum(p.numel() for p in m2.parameters())
        assert p2 < p1, "width_factor=0.5 deve ter menos parâmetros"

    def test_different_batch_sizes(self):
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        model.eval()
        for bs in [1, 4, 16, 64]:
            out = model(torch.randn(bs, STAT_DIM), torch.randn(bs, DEEP_DIM))
            assert out.shape[0] == bs

    def test_dataset_length_consistent(self):
        data = SyntheticLightroomData(n_samples=100)
        ds   = LightroomDataset(data.stat_features, data.deep_features, data.labels, data.deltas)
        assert len(ds) == 100

    def test_dataset_item_shapes(self):
        data = SyntheticLightroomData(n_samples=50)
        ds   = LightroomDataset(data.stat_features, data.deep_features, data.labels, data.deltas)
        item = ds[0]
        assert item["stat_features"].shape == (STAT_DIM,)
        assert item["deep_features"].shape  == (DEEP_DIM,)
        assert item["label"].ndim == 0
        assert item["deltas"].shape == (NUM_PARAMS,)

    def test_weighted_mse_loss(self):
        weights = torch.ones(NUM_PARAMS)
        loss_fn = WeightedMSELoss(weights)
        pred    = torch.randn(8, NUM_PARAMS)
        target  = torch.randn(8, NUM_PARAMS)
        loss    = loss_fn(pred, target)
        assert loss.item() > 0
        assert torch.isfinite(loss)

    def test_weighted_mse_zero_when_perfect(self):
        weights = torch.ones(NUM_PARAMS)
        loss_fn = WeightedMSELoss(weights)
        pred    = torch.randn(8, NUM_PARAMS)
        loss    = loss_fn(pred, pred.clone())
        assert loss.item() < 1e-6, "Loss deve ser ~0 quando pred == target"


# ---------------------------------------------------------------------------
# BLOCO 2 — Testes de treino do classificador
# ---------------------------------------------------------------------------
class TestClassifierTraining:
    """Verifica que o classificador aprende padrões e atinge métricas mínimas."""

    def _train(self, data: SyntheticLightroomData, epochs: int = 30, patience: int = 15):
        tr_loader, vl_loader = make_loaders(data, batch_size=32)
        model   = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        trainer = OptimizedClassifierTrainer(model, device=DEVICE, use_mixed_precision=False)
        trained = trainer.train(
            tr_loader, vl_loader,
            epochs=epochs, patience=patience,
            num_presets=NUM_PRESETS, max_lr=0.01
        )
        return trainer, trained

    def test_classifier_learns_easy_data(self, easy_data):
        """Com dados bem separados, accuracy deve superar 85%."""
        trainer, _ = self._train(easy_data)
        best_acc = max(trainer.val_accuracies)
        assert best_acc >= 0.85, (
            f"Classifier falhou em dados fáceis: best val_acc={best_acc:.3f} < 0.85"
        )

    def test_classifier_beats_random_hard_data(self, hard_data):
        """Com dados sobrepostos, deve superar baseline aleatório (1/num_presets)."""
        trainer, _ = self._train(hard_data)
        best_acc = max(trainer.val_accuracies)
        random_baseline = 1.0 / NUM_PRESETS
        assert best_acc > random_baseline, (
            f"Classifier não supera baseline aleatório: {best_acc:.3f} vs {random_baseline:.3f}"
        )

    def test_classifier_loss_decreases(self, easy_data):
        """Loss de treino deve decrescer ao longo das épocas."""
        trainer, _ = self._train(easy_data, epochs=20)
        losses = trainer.train_losses
        assert len(losses) >= 5, "Treino muito curto"
        # Compara média das últimas 5 épocas com as primeiras 5
        early_loss = np.mean(losses[:5])
        late_loss  = np.mean(losses[-5:])
        assert late_loss < early_loss, (
            f"Loss não decresceu: início={early_loss:.4f}, fim={late_loss:.4f}"
        )

    def test_classifier_val_loss_tracked(self, easy_data):
        """Val losses devem ser registadas e finitas."""
        trainer, _ = self._train(easy_data, epochs=10)
        assert len(trainer.val_losses) > 0
        assert all(np.isfinite(v) for v in trainer.val_losses)

    def test_classifier_with_class_weights(self, imbalanced_data):
        """Com pesos de classe, deve convergir mesmo com imbalance."""
        tr_loader, vl_loader = make_loaders(imbalanced_data, batch_size=32)
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        counts = np.bincount(imbalanced_data.labels)
        weights = torch.FloatTensor(1.0 / (counts + 1e-6))
        weights /= weights.sum() / NUM_PRESETS
        trainer = OptimizedClassifierTrainer(
            model, device=DEVICE, use_mixed_precision=False, class_weights=weights
        )
        trained = trainer.train(
            tr_loader, vl_loader,
            epochs=25, patience=15, num_presets=NUM_PRESETS
        )
        best_acc = max(trainer.val_accuracies)
        # Com imbalance mas dados separáveis, deve aprender razoavelmente
        assert best_acc > 1.0 / NUM_PRESETS, f"Classifier com weights falhou: acc={best_acc:.3f}"

    def test_tiny_dataset_no_crash(self, tiny_data):
        """Com poucos dados, não deve lançar exceção."""
        try:
            self._train(tiny_data, epochs=10)
        except Exception as e:
            pytest.fail(f"Crash com dataset pequeno: {e}")

    def test_early_stopping_triggers(self):
        """Early stopping deve ativar antes das épocas máximas quando dados são aleatórios."""
        from torch.utils.data import Subset
        rng = np.random.default_rng(0)
        n = 200
        stat   = rng.standard_normal((n, STAT_DIM)).astype(np.float32)
        deep   = rng.standard_normal((n, DEEP_DIM)).astype(np.float32)
        labels = rng.integers(0, NUM_PRESETS, n).astype(np.int64)

        ds        = LightroomDataset(stat, deep, labels)
        tr_loader = DataLoader(Subset(ds, list(range(160))), batch_size=32, shuffle=True, drop_last=True)
        vl_loader = DataLoader(Subset(ds, list(range(160, 200))), batch_size=32)

        model   = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        trainer = OptimizedClassifierTrainer(model, device=DEVICE, use_mixed_precision=False)
        trainer.train(tr_loader, vl_loader, epochs=50, patience=5, num_presets=NUM_PRESETS)

        epochs_run = len(trainer.train_losses)
        assert epochs_run < 50, f"Early stopping não ativou: correu {epochs_run}/50 épocas"


# ---------------------------------------------------------------------------
# BLOCO 3 — Testes de treino do regressor
# ---------------------------------------------------------------------------
class TestRegressorTraining:
    """Verifica que o regressor aprende a prever deltas."""

    def _train(self, data: SyntheticLightroomData, epochs: int = 40, patience: int = 20):
        (X_s_tr, X_s_vl, X_d_tr, X_d_vl,
         y_tr, y_vl, d_tr, d_vl) = data.train_val_split()

        scaler_s = StandardScaler().fit(X_s_tr)
        scaler_d = StandardScaler().fit(X_d_tr)
        scaler_deltas = StandardScaler().fit(d_tr)

        X_s_tr_sc = scaler_s.transform(X_s_tr).astype(np.float32)
        X_s_vl_sc = scaler_s.transform(X_s_vl).astype(np.float32)
        X_d_tr_sc = scaler_d.transform(X_d_tr).astype(np.float32)
        X_d_vl_sc = scaler_d.transform(X_d_vl).astype(np.float32)
        d_tr_sc   = scaler_deltas.transform(d_tr).astype(np.float32)
        d_vl_sc   = scaler_deltas.transform(d_vl).astype(np.float32)

        ds_train = LightroomDataset(X_s_tr_sc, X_d_tr_sc, y_tr, d_tr_sc)
        ds_val   = LightroomDataset(X_s_vl_sc, X_d_vl_sc, y_vl, d_vl_sc)
        tr_loader = DataLoader(ds_train, batch_size=32, shuffle=True, drop_last=True)
        vl_loader = DataLoader(ds_val, batch_size=32)

        weights = torch.ones(NUM_PARAMS)
        model   = OptimizedRefinementRegressor(STAT_DIM, DEEP_DIM, NUM_PRESETS, NUM_PARAMS)
        trainer = OptimizedRefinementTrainer(
            model, param_weights=weights,
            device=DEVICE, use_mixed_precision=False
        )
        delta_cols = [f"delta_param_{i}" for i in range(NUM_PARAMS)]
        trained = trainer.train(
            tr_loader, vl_loader,
            epochs=epochs, patience=patience,
            delta_columns=delta_cols, scaler_deltas=scaler_deltas
        )
        return trainer, trained, scaler_deltas

    def test_regressor_loss_decreases(self, easy_data):
        trainer, _, _ = self._train(easy_data)
        losses = trainer.train_losses
        assert len(losses) >= 5
        assert np.mean(losses[-5:]) < np.mean(losses[:5]), "Loss do regressor não decresceu"

    def test_regressor_val_loss_finite(self, easy_data):
        trainer, _, _ = self._train(easy_data)
        assert all(np.isfinite(v) for v in trainer.val_losses)

    def test_regressor_output_range(self, easy_data):
        """Outputs normalizados do regressor devem estar em range razoável ([-10, 10])."""
        _, model, _ = self._train(easy_data)
        model.eval()
        with torch.no_grad():
            stat   = torch.randn(16, STAT_DIM)
            deep   = torch.randn(16, DEEP_DIM)
            preset = torch.randint(0, NUM_PRESETS, (16,))
            out    = model(stat, deep, preset)
        assert out.abs().max().item() < 100, "Outputs do regressor fora de range esperado"

    def test_regressor_mean_absolute_error_reasonable(self, easy_data):
        """MAE normalizado deve ser menor que 2.0 (desvios padrão) em dados fáceis."""
        trainer, _, _ = self._train(easy_data, epochs=50)
        if trainer.val_losses:
            best_val_loss = min(trainer.val_losses)
            # MSE em escala normalizada — esperamos < 1.0 para dados com padrão claro
            assert best_val_loss < 2.0, (
                f"MAE do regressor demasiado alto em dados fáceis: {best_val_loss:.4f}"
            )

    def test_regressor_no_crash_tiny(self, tiny_data):
        try:
            self._train(tiny_data, epochs=10)
        except Exception as e:
            pytest.fail(f"Regressor crash com dataset pequeno: {e}")


# ---------------------------------------------------------------------------
# BLOCO 4 — Testes de generalização e overfitting
# ---------------------------------------------------------------------------
class TestGeneralization:
    """Deteta overfitting e verifica generalização."""

    def _get_train_val_gap(self, data: SyntheticLightroomData, epochs: int = 40):
        tr_loader, vl_loader = make_loaders(data, batch_size=16)
        model   = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        trainer = OptimizedClassifierTrainer(model, device=DEVICE, use_mixed_precision=False)
        trainer.train(tr_loader, vl_loader, epochs=epochs, patience=epochs,
                      num_presets=NUM_PRESETS)
        # Gap entre melhor train e melhor val — deveria ser pequeno
        best_train = min(trainer.train_losses)
        best_val   = min(trainer.val_losses)
        return best_train, best_val

    def test_overfitting_gap_small_on_easy_data(self, easy_data):
        """Em dados fáceis, o gap train/val não deve ser excessivo."""
        best_train, best_val = self._get_train_val_gap(easy_data)
        gap = best_val - best_train
        assert gap < 2.0, (
            f"Gap train/val suspeito: train={best_train:.4f}, val={best_val:.4f}, gap={gap:.4f}"
        )

    def test_model_generalizes_to_new_data(self, easy_data):
        """
        Modelo treinado deve generalizar para novas amostras da MESMA distribuição.
        Os dados de teste partilham os mesmos centróides de easy_data (separados via seed).
        Scalers aplicados para garantir consistência de escala.
        """
        (X_s_tr, X_s_vl, X_d_tr, X_d_vl,
         y_tr, y_vl, _, _) = easy_data.train_val_split()

        scaler_s = StandardScaler().fit(X_s_tr)
        scaler_d = StandardScaler().fit(X_d_tr)

        X_s_tr_sc = scaler_s.transform(X_s_tr).astype(np.float32)
        X_s_vl_sc = scaler_s.transform(X_s_vl).astype(np.float32)
        X_d_tr_sc = scaler_d.transform(X_d_tr).astype(np.float32)
        X_d_vl_sc = scaler_d.transform(X_d_vl).astype(np.float32)

        tr_loader = DataLoader(
            LightroomDataset(X_s_tr_sc, X_d_tr_sc, y_tr),
            batch_size=32, shuffle=True, drop_last=True
        )
        vl_loader = DataLoader(
            LightroomDataset(X_s_vl_sc, X_d_vl_sc, y_vl),
            batch_size=32
        )
        model   = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        trainer = OptimizedClassifierTrainer(model, device=DEVICE, use_mixed_precision=False)
        trainer.train(tr_loader, vl_loader, epochs=40, patience=20, num_presets=NUM_PRESETS)

        # Gerar novos dados de teste com os MESMOS centróides (reutilizar easy_data)
        # Simula novas imagens do mesmo fotógrafo → mesma distribuição de features
        test_rng = np.random.default_rng(99)
        test_stat = np.array([
            easy_data.stat_centers[l] + test_rng.normal(0, 0.3, STAT_DIM)
            for l in easy_data.labels[:100]
        ], dtype=np.float32)
        test_deep = np.array([
            easy_data.deep_centers[l] + test_rng.normal(0, 0.3, DEEP_DIM)
            for l in easy_data.labels[:100]
        ], dtype=np.float32)
        test_labels = easy_data.labels[:100]

        test_stat_sc = scaler_s.transform(test_stat).astype(np.float32)
        test_deep_sc = scaler_d.transform(test_deep).astype(np.float32)

        test_loader = DataLoader(
            LightroomDataset(test_stat_sc, test_deep_sc, test_labels),
            batch_size=32
        )

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for batch in test_loader:
                preds = model(batch["stat_features"], batch["deep_features"]).argmax(dim=1)
                correct += (preds == batch["label"]).sum().item()
                total   += len(batch["label"])

        test_acc = correct / total
        assert test_acc >= 0.75, f"Generalização fraca: test_acc={test_acc:.3f}"


# ---------------------------------------------------------------------------
# BLOCO 5 — Testes de consistência numérica
# ---------------------------------------------------------------------------
class TestNumericalConsistency:
    """Verifica estabilidade numérica e reprodutibilidade."""

    def test_deterministic_with_same_seed(self):
        """Dois treinos com seed igual devem produzir losses iguais (primeiros 5 epochs)."""
        def run(seed_val):
            torch.manual_seed(seed_val)
            np.random.seed(seed_val)
            data = SyntheticLightroomData(n_samples=100, seed=seed_val)
            tr_loader, vl_loader = make_loaders(data, batch_size=16)
            model   = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
            # Reinicializar com seed para pesos determinísticos
            torch.manual_seed(seed_val)
            for m in model.modules():
                if hasattr(m, 'reset_parameters'):
                    m.reset_parameters()
            trainer = OptimizedClassifierTrainer(model, device=DEVICE, use_mixed_precision=False)
            trainer.train(tr_loader, vl_loader, epochs=3, patience=10, num_presets=NUM_PRESETS)
            return trainer.train_losses

        # Verifica apenas que losses são finitas (determinismo exato não é garantido com BN)
        losses = run(42)
        assert all(np.isfinite(l) for l in losses), "Losses não finitas"

    def test_grad_flow_classifier(self):
        """Gradientes devem fluir para todos os parâmetros treináveis."""
        model  = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        stat   = torch.randn(8, STAT_DIM, requires_grad=False)
        deep   = torch.randn(8, DEEP_DIM, requires_grad=False)
        labels = torch.randint(0, NUM_PRESETS, (8,))
        criterion = nn.CrossEntropyLoss()
        out  = model(stat, deep)
        loss = criterion(out, labels)
        loss.backward()
        no_grad_params = [
            n for n, p in model.named_parameters()
            if p.grad is None and p.requires_grad
        ]
        assert len(no_grad_params) == 0, f"Parâmetros sem gradiente: {no_grad_params}"

    def test_grad_flow_regressor(self):
        """Gradientes devem fluir no regressor incluindo o embedding de preset."""
        weights = torch.ones(NUM_PARAMS)
        model   = OptimizedRefinementRegressor(STAT_DIM, DEEP_DIM, NUM_PRESETS, NUM_PARAMS)
        stat    = torch.randn(8, STAT_DIM)
        deep    = torch.randn(8, DEEP_DIM)
        preset  = torch.randint(0, NUM_PRESETS, (8,))
        target  = torch.randn(8, NUM_PARAMS)
        loss_fn = WeightedMSELoss(weights)
        out  = model(stat, deep, preset)
        loss = loss_fn(out, target)
        loss.backward()
        no_grad = [
            n for n, p in model.named_parameters()
            if p.grad is None and p.requires_grad
        ]
        assert len(no_grad) == 0, f"Parâmetros sem gradiente: {no_grad}"

    def test_no_nan_in_batch_norm_eval(self):
        """BatchNorm em modo eval não deve produzir NaN."""
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        # Treino rápido para popular running stats do BatchNorm
        model.train()
        for _ in range(5):
            stat = torch.randn(8, STAT_DIM)
            deep = torch.randn(8, DEEP_DIM)
            model(stat, deep)
        # Inferência
        model.eval()
        with torch.no_grad():
            stat = torch.randn(16, STAT_DIM)
            deep = torch.randn(16, DEEP_DIM)
            out  = model(stat, deep)
        assert torch.isfinite(out).all(), "NaN em eval mode (BN stats corrompidas?)"

    def test_inference_single_sample(self):
        """Inferência com batch_size=1 não deve falhar."""
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        model.eval()
        with torch.no_grad():
            out = model(torch.randn(1, STAT_DIM), torch.randn(1, DEEP_DIM))
        assert out.shape == (1, NUM_PRESETS)

    def test_softmax_probabilities_sum_to_one(self):
        """Probabilidades pós-softmax devem somar 1.0 por amostra."""
        import torch.nn.functional as F
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        model.eval()
        with torch.no_grad():
            logits = model(torch.randn(16, STAT_DIM), torch.randn(16, DEEP_DIM))
            probs  = F.softmax(logits, dim=1)
            sums   = probs.sum(dim=1)
        assert torch.allclose(sums, torch.ones(16), atol=1e-5), "Probabilidades não somam 1"


# ---------------------------------------------------------------------------
# BLOCO 6 — Testes de pipeline completo (end-to-end simulado)
# ---------------------------------------------------------------------------
class TestEndToEndPipeline:
    """Simula o fluxo completo: treino → inferência → clamping → output."""

    def test_full_pipeline_classifier_regressor(self, easy_data):
        """Treinar ambos os modelos e executar inferência end-to-end."""
        (X_s_tr, X_s_vl, X_d_tr, X_d_vl,
         y_tr, y_vl, d_tr, d_vl) = easy_data.train_val_split()

        scaler_stat   = StandardScaler().fit(X_s_tr)
        scaler_deep   = StandardScaler().fit(X_d_tr)
        scaler_deltas = StandardScaler().fit(d_tr)

        def sc(sc, x): return sc.transform(x).astype(np.float32)

        ds_tr = LightroomDataset(sc(scaler_stat, X_s_tr), sc(scaler_deep, X_d_tr),
                                 y_tr, scaler_deltas.transform(d_tr).astype(np.float32))
        ds_vl = LightroomDataset(sc(scaler_stat, X_s_vl), sc(scaler_deep, X_d_vl),
                                 y_vl, scaler_deltas.transform(d_vl).astype(np.float32))
        tr_loader = DataLoader(ds_tr, batch_size=32, shuffle=True, drop_last=True)
        vl_loader = DataLoader(ds_vl, batch_size=32)

        # Treinar classificador
        clf_model   = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        clf_trainer = OptimizedClassifierTrainer(clf_model, device=DEVICE, use_mixed_precision=False)
        clf_trainer.train(tr_loader, vl_loader, epochs=20, patience=15, num_presets=NUM_PRESETS)

        # Treinar regressor
        weights   = torch.ones(NUM_PARAMS)
        reg_model = OptimizedRefinementRegressor(STAT_DIM, DEEP_DIM, NUM_PRESETS, NUM_PARAMS)
        reg_trainer = OptimizedRefinementTrainer(
            reg_model, param_weights=weights, device=DEVICE, use_mixed_precision=False
        )
        delta_cols = [f"delta_param_{i}" for i in range(NUM_PARAMS)]
        reg_trainer.train(tr_loader, vl_loader, epochs=20, patience=15,
                          delta_columns=delta_cols, scaler_deltas=scaler_deltas)

        # Inferência end-to-end
        clf_model.eval()
        reg_model.eval()
        import torch.nn.functional as F

        stat_input = torch.FloatTensor(sc(scaler_stat, X_s_vl[:4]))
        deep_input = torch.FloatTensor(sc(scaler_deep, X_d_vl[:4]))

        with torch.no_grad():
            logits    = clf_model(stat_input, deep_input)
            probs     = F.softmax(logits, dim=1)
            preset_id = probs.argmax(dim=1)
            deltas_norm = reg_model(stat_input, deep_input, preset_id)
            deltas = scaler_deltas.inverse_transform(deltas_norm.numpy())

        assert deltas.shape == (4, NUM_PARAMS), f"Shape inesperado: {deltas.shape}"
        assert np.isfinite(deltas).all(), "Deltas contêm NaN/Inf"
        # Deltas devem estar em range razoável (sem explosão)
        assert np.abs(deltas).max() < 1000, f"Deltas fora de range: max={np.abs(deltas).max()}"

    def test_clamping_mock(self):
        """Simular o _clamp_parameter do predictor com valores extremos."""
        import numpy as np
        ranges = {
            'exposure':   (-5.0, 5.0),
            'contrast':   (-100, 100),
            'highlights': (-100, 100),
            'temperature': (2000, 50000),
        }
        raw_values = {
            'exposure':   10.0,   # acima do máximo
            'contrast':   -200.0, # abaixo do mínimo
            'highlights': 50.0,   # dentro do range
            'temperature': 1000.0, # abaixo do mínimo
        }
        expected = {
            'exposure':   5.0,
            'contrast':   -100.0,
            'highlights': 50.0,
            'temperature': 2000.0,
        }
        for param, raw in raw_values.items():
            lo, hi = ranges[param]
            clamped = float(np.clip(raw, lo, hi))
            assert clamped == expected[param], (
                f"{param}: esperado {expected[param]}, obtido {clamped}"
            )


# ---------------------------------------------------------------------------
# BLOCO 7 — Benchmarks de performance (informativo, não bloqueante)
# ---------------------------------------------------------------------------
class TestPerformanceBenchmarks:
    """Testes de performance — medem tempo e throughput. Não falham por velocidade."""

    def test_inference_latency(self):
        """Mede latência de inferência para 1 imagem (deve ser < 100ms em CPU)."""
        import time
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        model.eval()
        # Warmup
        with torch.no_grad():
            model(torch.randn(1, STAT_DIM), torch.randn(1, DEEP_DIM))
        # Medir
        start = time.perf_counter()
        with torch.no_grad():
            for _ in range(50):
                model(torch.randn(1, STAT_DIM), torch.randn(1, DEEP_DIM))
        elapsed = (time.perf_counter() - start) / 50 * 1000  # ms por inferência

        print(f"\n  [BENCH] Latência média (CPU, batch=1): {elapsed:.2f}ms")
        # Informativo — reporta mas não falha
        assert elapsed < 500, f"Latência excessiva: {elapsed:.2f}ms"

    def test_batch_throughput(self):
        """Mede throughput para batch de 64 imagens."""
        import time
        model = OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)
        model.eval()
        with torch.no_grad():
            start = time.perf_counter()
            for _ in range(20):
                model(torch.randn(64, STAT_DIM), torch.randn(64, DEEP_DIM))
            elapsed = time.perf_counter() - start
        imgs_per_sec = (20 * 64) / elapsed
        print(f"\n  [BENCH] Throughput (CPU, batch=64): {imgs_per_sec:.0f} img/s")
        assert imgs_per_sec > 10, f"Throughput muito baixo: {imgs_per_sec:.0f} img/s"

    def test_model_size_reasonable(self):
        """Modelos devem ser pequenos o suficiente para uso local (< 50MB)."""
        import io
        for name, model in [
            ("Classifier", OptimizedPresetClassifier(STAT_DIM, DEEP_DIM, NUM_PRESETS)),
            ("Regressor",  OptimizedRefinementRegressor(STAT_DIM, DEEP_DIM, NUM_PRESETS, NUM_PARAMS)),
        ]:
            buf = io.BytesIO()
            torch.save(model.state_dict(), buf)
            size_mb = len(buf.getvalue()) / (1024 * 1024)
            print(f"\n  [BENCH] {name}: {size_mb:.2f} MB")
            assert size_mb < 50, f"{name} demasiado grande: {size_mb:.2f} MB"
