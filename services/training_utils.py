# -*- coding: utf-8 -*-
"""
Training Utilities
Mixed Precision Training, Gradient Accumulation, e outras utilidades

Data: 16 Novembro 2025
"""

import torch
import torch.nn as nn
from torch.cuda.amp import GradScaler, autocast
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class MixedPrecisionTrainer:
    """
    Wrapper para Mixed Precision Training (FP16)

    Benefícios:
    - Treino 2-3x mais rápido em GPUs modernas
    - Reduz uso de memória em ~50%
    - Permite batch sizes maiores
    """

    def __init__(
        self,
        enabled: bool = True,
        device: str = "cuda"
    ):
        """
        Args:
            enabled: Ativar mixed precision
            device: Dispositivo (cuda/cpu/mps)
        """
        self.enabled = enabled and device == "cuda"  # Mixed precision apenas em CUDA

        if self.enabled:
            self.scaler = GradScaler()
            logger.info("✅ Mixed Precision Training ATIVADO (FP16)")
        else:
            self.scaler = None
            if device == "cuda":
                logger.info("ℹ️ Mixed Precision Training DESATIVADO")
            else:
                logger.info(f"ℹ️ Mixed Precision não disponível em {device}")

    def __call__(self, func):
        """
        Decorator para usar mixed precision em uma função de treino

        Uso:
            mp_trainer = MixedPrecisionTrainer()

            @mp_trainer
            def train_step(model, inputs, labels):
                outputs = model(inputs)
                loss = criterion(outputs, labels)
                return loss
        """
        if not self.enabled:
            return func  # Sem mixed precision, retorna função original

        def wrapper(*args, **kwargs):
            with autocast():
                return func(*args, **kwargs)
        return wrapper

    def step(
        self,
        loss: torch.Tensor,
        optimizer: torch.optim.Optimizer,
        retain_graph: bool = False,
        clip_grad_norm: Optional[float] = None,
        parameters: Optional[nn.Module] = None
    ):
        """
        Executa backward pass e optimizer step com mixed precision

        Args:
            loss: Tensor de loss
            optimizer: Otimizador
            retain_graph: Manter grafo de computação
            clip_grad_norm: Clipar gradientes (opcional)
            parameters: Parâmetros do modelo (para gradient clipping)
        """
        if self.enabled:
            # Backward com scaling
            self.scaler.scale(loss).backward(retain_graph=retain_graph)

            # Gradient clipping (se especificado)
            if clip_grad_norm is not None and parameters is not None:
                self.scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(parameters, clip_grad_norm)

            # Optimizer step
            self.scaler.step(optimizer)
            self.scaler.update()
        else:
            # Backward normal
            loss.backward(retain_graph=retain_graph)

            # Gradient clipping
            if clip_grad_norm is not None and parameters is not None:
                torch.nn.utils.clip_grad_norm_(parameters, clip_grad_norm)

            # Optimizer step
            optimizer.step()

    def context(self):
        """
        Context manager para mixed precision

        Uso:
            with mp_trainer.context():
                outputs = model(inputs)
                loss = criterion(outputs, labels)
        """
        if self.enabled:
            return autocast()
        else:
            # No-op context manager
            return _DummyContext()


class _DummyContext:
    """Context manager dummy (não faz nada)"""
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class GradientAccumulator:
    """
    Gradient Accumulation para simular batch sizes maiores

    Útil quando:
    - Memória GPU limitada
    - Batch size ideal > memória disponível
    - Queres estabilidade de batch grande com hardware limitado
    """

    def __init__(
        self,
        accumulation_steps: int = 1,
        max_grad_norm: Optional[float] = None
    ):
        """
        Args:
            accumulation_steps: Número de passos para acumular gradientes
            max_grad_norm: Norma máxima para gradient clipping
        """
        self.accumulation_steps = accumulation_steps
        self.max_grad_norm = max_grad_norm
        self.current_step = 0

        if accumulation_steps > 1:
            logger.info(f"✅ Gradient Accumulation ATIVADO ({accumulation_steps} steps)")
            logger.info(f"   Batch Size Efetivo = Batch Size × {accumulation_steps}")

    def step(
        self,
        loss: torch.Tensor,
        optimizer: torch.optim.Optimizer,
        model: nn.Module,
        scaler: Optional[GradScaler] = None
    ) -> bool:
        """
        Executa passo de gradient accumulation

        Args:
            loss: Loss do batch atual
            optimizer: Otimizador
            model: Modelo
            scaler: GradScaler para mixed precision (opcional)

        Returns:
            True se optimizer step foi executado, False caso contrário
        """
        # Normalizar loss pelo número de accumulation steps
        loss = loss / self.accumulation_steps

        # Backward
        if scaler is not None:
            scaler.scale(loss).backward()
        else:
            loss.backward()

        # Incrementar contador
        self.current_step += 1

        # Verificar se deve fazer optimizer step
        if self.current_step % self.accumulation_steps == 0:
            # Gradient clipping
            if self.max_grad_norm is not None:
                if scaler is not None:
                    scaler.unscale_(optimizer)

                torch.nn.utils.clip_grad_norm_(
                    model.parameters(),
                    self.max_grad_norm
                )

            # Optimizer step
            if scaler is not None:
                scaler.step(optimizer)
                scaler.update()
            else:
                optimizer.step()

            # Zero gradients
            optimizer.zero_grad()

            return True  # Step executado

        return False  # Step não executado (acumulando)

    def should_step(self) -> bool:
        """Verifica se deve executar optimizer step"""
        return self.current_step % self.accumulation_steps == 0

    def reset(self):
        """Reset contador"""
        self.current_step = 0


class TrainingEnhancer:
    """
    Wrapper que combina Mixed Precision + Gradient Accumulation

    Uso simplificado de todas as técnicas de otimização
    """

    def __init__(
        self,
        use_amp: bool = True,
        device: str = "cuda",
        accumulation_steps: int = 1,
        max_grad_norm: Optional[float] = 1.0
    ):
        """
        Args:
            use_amp: Usar mixed precision
            device: Dispositivo
            accumulation_steps: Steps de gradient accumulation
            max_grad_norm: Gradient clipping norm
        """
        self.device = device

        # Mixed Precision
        self.mp_trainer = MixedPrecisionTrainer(
            enabled=use_amp,
            device=device
        )

        # Gradient Accumulation
        self.accumulator = GradientAccumulator(
            accumulation_steps=accumulation_steps,
            max_grad_norm=max_grad_norm
        )

        # Scaler (se mixed precision ativado)
        self.scaler = self.mp_trainer.scaler

        logger.info("🚀 TrainingEnhancer inicializado")
        logger.info(f"   Mixed Precision: {'✅' if self.mp_trainer.enabled else '❌'}")
        logger.info(f"   Gradient Accumulation: {accumulation_steps} steps")
        logger.info(f"   Gradient Clipping: {'✅' if max_grad_norm else '❌'}")

    def train_step(
        self,
        model: nn.Module,
        inputs: torch.Tensor,
        labels: torch.Tensor,
        criterion: nn.Module,
        optimizer: torch.optim.Optimizer
    ) -> Dict[str, Any]:
        """
        Executa um passo de treino completo com todas as otimizações

        Args:
            model: Modelo
            inputs: Inputs do batch
            labels: Labels do batch
            criterion: Função de perda
            optimizer: Otimizador

        Returns:
            Dict com informações do step
        """
        # Forward pass com mixed precision
        with self.mp_trainer.context():
            outputs = model(inputs)
            loss = criterion(outputs, labels)

        # Backward + Optimizer step com gradient accumulation
        optimizer_stepped = self.accumulator.step(
            loss=loss,
            optimizer=optimizer,
            model=model,
            scaler=self.scaler
        )

        return {
            'loss': loss.item() * self.accumulator.accumulation_steps,  # Loss não normalizado
            'optimizer_stepped': optimizer_stepped
        }

    def context(self):
        """Context manager para mixed precision"""
        return self.mp_trainer.context()


def create_training_enhancer(
    config: Dict[str, Any],
    device: str = "cuda"
) -> TrainingEnhancer:
    """
    Factory function para criar TrainingEnhancer a partir de config

    Args:
        config: Dicionário de configuração
        device: Dispositivo

    Returns:
        TrainingEnhancer configurado
    """
    use_amp = config.get('use_mixed_precision', True)
    accumulation_steps = config.get('gradient_accumulation_steps', 1)
    max_grad_norm = config.get('max_grad_norm', 1.0)

    return TrainingEnhancer(
        use_amp=use_amp,
        device=device,
        accumulation_steps=accumulation_steps,
        max_grad_norm=max_grad_norm
    )


# Exemplo de uso
if __name__ == "__main__":
    print("=" * 80)
    print("TRAINING UTILITIES - Exemplo de Uso")
    print("=" * 80)
    print()

    print("# 1. Mixed Precision Training")
    print("-" * 80)
    print("""
from services.training_utils import MixedPrecisionTrainer

mp_trainer = MixedPrecisionTrainer(enabled=True, device='cuda')

# Método 1: Context manager
with mp_trainer.context():
    outputs = model(inputs)
    loss = criterion(outputs, labels)

mp_trainer.step(loss, optimizer, clip_grad_norm=1.0, parameters=model.parameters())

# Método 2: Decorator
@mp_trainer
def forward_pass(model, inputs):
    return model(inputs)
    """)

    print()
    print("# 2. Gradient Accumulation")
    print("-" * 80)
    print("""
from services.training_utils import GradientAccumulator

accumulator = GradientAccumulator(accumulation_steps=4)

for batch in dataloader:
    loss = compute_loss(batch)

    # step() retorna True quando optimizer step é executado
    if accumulator.step(loss, optimizer, model):
        print("Optimizer step executado!")
    """)

    print()
    print("# 3. TrainingEnhancer (Mixed Precision + Gradient Accumulation)")
    print("-" * 80)
    print("""
from services.training_utils import TrainingEnhancer

enhancer = TrainingEnhancer(
    use_amp=True,
    device='cuda',
    accumulation_steps=4,
    max_grad_norm=1.0
)

for batch in dataloader:
    inputs, labels = batch
    result = enhancer.train_step(model, inputs, labels, criterion, optimizer)

    if result['optimizer_stepped']:
        print(f"Loss: {result['loss']:.4f}")
    """)

    print()
    print("=" * 80)
