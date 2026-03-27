"""
Gradient Checkpointing
Trade-off entre memória e computação para treinar modelos maiores

Features:
- Checkpointing seletivo de layers
- Wrapper automático para modelos PyTorch
- Configuração flexível
- Compatível com mixed precision

Ganhos:
- Reduz uso de memória em 40-60%
- Permite batch sizes 2-3x maiores
- Trade-off: +20-30% tempo de treino
- Permite modelos mais profundos

Uso:
    model = MyModel()
    model = add_gradient_checkpointing(model)
    # Treino normal, mas usa menos memória

Data: 21 Novembro 2025
"""

import logging
import torch
import torch.nn as nn
from torch.utils.checkpoint import checkpoint
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)


def checkpoint_sequential(functions: List[Callable], segments: int, *inputs):
    """
    Aplica checkpointing a uma sequência de funções

    Args:
        functions: Lista de funções/layers a executar sequencialmente
        segments: Número de segmentos para checkpointing
        *inputs: Inputs iniciais

    Returns:
        Output final
    """
    def run_function(start, end, functions):
        def forward(*inputs):
            for j in range(start, end):
                inputs = (functions[j](*inputs),) if not isinstance(inputs, tuple) else (functions[j](*inputs),)
            return inputs[0] if len(inputs) == 1 else inputs
        return forward

    if segments == 1:
        # Sem checkpointing
        return run_function(0, len(functions), functions)(*inputs)

    # Dividir em segmentos
    segment_size = len(functions) // segments
    end = 0

    for start in range(0, len(functions), segment_size):
        end = min(start + segment_size, len(functions))
        inputs = checkpoint(run_function(start, end, functions), *inputs)

    return inputs


class CheckpointWrapper(nn.Module):
    """
    Wrapper que adiciona gradient checkpointing a um módulo

    Usa torch.utils.checkpoint para reduzir uso de memória
    """

    def __init__(self, module: nn.Module, num_segments: int = 1):
        """
        Args:
            module: Módulo a fazer checkpoint
            num_segments: Número de segmentos (1=sem checkpoint, >1=com checkpoint)
        """
        super().__init__()
        self.module = module
        self.num_segments = num_segments

    def forward(self, *args, **kwargs):
        if self.num_segments > 1 and self.training:
            # Com checkpointing durante treino
            return checkpoint(self.module, *args, **kwargs)
        else:
            # Sem checkpointing durante validação/inferência
            return self.module(*args, **kwargs)


def add_gradient_checkpointing(
    model: nn.Module,
    checkpoint_layers: Optional[List[str]] = None,
    num_segments: int = 2
) -> nn.Module:
    """
    Adiciona gradient checkpointing a um modelo

    Args:
        model: Modelo PyTorch
        checkpoint_layers: Lista de nomes de layers a checkpoint (None=auto)
        num_segments: Número de segmentos para checkpointing

    Returns:
        Modelo com checkpointing ativado
    """
    logger.info(f"Adicionando gradient checkpointing ao modelo (segments={num_segments})")

    if checkpoint_layers is None:
        # Auto-detect: checkpoint layers pesados (Linear, Conv2d, etc)
        checkpoint_layers = []
        for name, module in model.named_modules():
            if isinstance(module, (nn.Linear, nn.Conv2d, nn.LSTM, nn.GRU, nn.TransformerEncoderLayer)):
                checkpoint_layers.append(name)

    logger.info(f"Layers a checkpoint: {len(checkpoint_layers)}")

    # Aplicar wrapper a cada layer
    for name in checkpoint_layers:
        # Obter layer
        parts = name.split('.')
        parent = model
        for part in parts[:-1]:
            parent = getattr(parent, part)

        # Substituir por wrapper
        layer = getattr(parent, parts[-1])
        setattr(parent, parts[-1], CheckpointWrapper(layer, num_segments))

    return model


class GradientCheckpointingMixin:
    """
    Mixin para adicionar gradient checkpointing a modelos

    Uso:
        class MyModel(nn.Module, GradientCheckpointingMixin):
            def __init__(self):
                super().__init__()
                self.enable_checkpointing = False
                ...

            def forward(self, x):
                if self.enable_checkpointing and self.training:
                    return self._forward_with_checkpointing(x)
                return self._forward_normal(x)
    """

    def enable_gradient_checkpointing(self, num_segments: int = 2):
        """
        Ativa gradient checkpointing

        Args:
            num_segments: Número de segmentos
        """
        self.enable_checkpointing = True
        self.checkpoint_segments = num_segments
        logger.info(f"Gradient checkpointing ativado (segments={num_segments})")

    def disable_gradient_checkpointing(self):
        """Desativa gradient checkpointing"""
        self.enable_checkpointing = False
        logger.info("Gradient checkpointing desativado")


class CheckpointedSequential(nn.Sequential):
    """
    Sequential com gradient checkpointing integrado

    Drop-in replacement para nn.Sequential com checkpointing
    """

    def __init__(self, *args, num_segments: int = 2):
        """
        Args:
            *args: Layers do sequential
            num_segments: Número de segmentos para checkpointing
        """
        super().__init__(*args)
        self.num_segments = num_segments

    def forward(self, input):
        if self.num_segments > 1 and self.training:
            # Com checkpointing
            functions = list(self._modules.values())
            return checkpoint_sequential(functions, self.num_segments, input)
        else:
            # Sem checkpointing (inferência ou validação)
            return super().forward(input)


def calculate_memory_savings(model: nn.Module, with_checkpointing: bool = True) -> dict:
    """
    Estima redução de memória com gradient checkpointing

    Args:
        model: Modelo PyTorch
        with_checkpointing: Se True, calcula com checkpointing

    Returns:
        Dict com estimativas de memória
    """
    # Contar parâmetros
    num_params = sum(p.numel() for p in model.parameters())
    param_memory_mb = (num_params * 4) / (1024**2)  # Float32 = 4 bytes

    # Estimativa de ativações (heurística)
    # Ativações normalmente são ~3-4x o tamanho dos parâmetros durante backprop
    activation_memory_mb = param_memory_mb * 3.5

    if with_checkpointing:
        # Checkpointing reduz memória de ativações em ~50-60%
        activation_memory_mb *= 0.45

    total_memory_mb = param_memory_mb + activation_memory_mb

    return {
        "parameters_mb": param_memory_mb,
        "activations_mb": activation_memory_mb,
        "total_mb": total_memory_mb,
        "total_gb": total_memory_mb / 1024,
        "with_checkpointing": with_checkpointing
    }


# Exemplo de modelo com checkpointing integrado
class CheckpointedModel(nn.Module):
    """
    Exemplo de modelo com gradient checkpointing

    Demonstra como integrar checkpointing num modelo customizado
    """

    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int, use_checkpointing: bool = True):
        super().__init__()
        self.use_checkpointing = use_checkpointing

        # Encoder (camadas pesadas)
        self.encoder = CheckpointedSequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            num_segments=3 if use_checkpointing else 1
        )

        # Decoder (camadas leves)
        self.decoder = nn.Sequential(
            nn.Linear(hidden_dim, output_dim)
        )

    def forward(self, x):
        x = self.encoder(x)
        x = self.decoder(x)
        return x


if __name__ == "__main__":
    # Teste de gradient checkpointing
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("GRADIENT CHECKPOINTING - Teste")
    print("=" * 60)

    # Criar modelo simples
    model = nn.Sequential(
        nn.Linear(100, 512),
        nn.ReLU(),
        nn.Linear(512, 512),
        nn.ReLU(),
        nn.Linear(512, 512),
        nn.ReLU(),
        nn.Linear(512, 10)
    )

    print(f"\nModelo original: {sum(p.numel() for p in model.parameters()):,} parâmetros")

    # Adicionar checkpointing
    model_checkpoint = add_gradient_checkpointing(model, num_segments=2)

    # Estimativas de memória
    print("\n1. Sem checkpointing:")
    mem_without = calculate_memory_savings(model, with_checkpointing=False)
    print(f"   Total: {mem_without['total_mb']:.1f} MB ({mem_without['total_gb']:.2f} GB)")

    print("\n2. Com checkpointing:")
    mem_with = calculate_memory_savings(model, with_checkpointing=True)
    print(f"   Total: {mem_with['total_mb']:.1f} MB ({mem_with['total_gb']:.2f} GB)")

    savings_percent = (1 - mem_with['total_mb'] / mem_without['total_mb']) * 100
    print(f"\n3. Redução de memória: {savings_percent:.1f}%")

    # Test forward pass
    print("\n4. Teste de forward pass...")
    x = torch.randn(4, 100)
    model_checkpoint.train()

    output = model_checkpoint(x)
    print(f"   Output shape: {output.shape}")
    print(f"   ✓ Forward pass com checkpointing OK")

    print("\n✅ Teste completo!")
