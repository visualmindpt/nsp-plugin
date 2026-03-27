# -*- coding: utf-8 -*-
"""
Learning Rate Finder
Implementação do método de Leslie Smith para encontrar LR ótimo

Data: 16 Novembro 2025
"""

import torch
import torch.nn as nn
import numpy as np
import matplotlib.pyplot as plt
from typing import Tuple, Optional, List
import logging
from copy import deepcopy

logger = logging.getLogger(__name__)


class LearningRateFinder:
    """
    Learning Rate Finder usando método de Leslie Smith

    Referência: "Cyclical Learning Rates for Training Neural Networks" (2017)
    """

    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        criterion: nn.Module,
        device: str = "cpu"
    ):
        """
        Args:
            model: Modelo PyTorch
            optimizer: Otimizador
            criterion: Função de perda
            device: Dispositivo (cpu/cuda/mps)
        """
        self.model = model
        self.optimizer = optimizer
        self.criterion = criterion
        self.device = device

        # Salvar estado inicial do modelo
        self.initial_state = deepcopy(model.state_dict())

        # Resultados
        self.learning_rates = []
        self.losses = []

    def range_test(
        self,
        train_loader: torch.utils.data.DataLoader,
        start_lr: float = 1e-7,
        end_lr: float = 10,
        num_iter: int = 100,
        smooth_f: float = 0.05,
        diverge_th: float = 5
    ) -> Tuple[float, List[float], List[float]]:
        """
        Executa o teste de range de learning rate

        Args:
            train_loader: DataLoader de treino
            start_lr: LR inicial (padrão: 1e-7)
            end_lr: LR final (padrão: 10)
            num_iter: Número de iterações (padrão: 100)
            smooth_f: Factor de suavização (padrão: 0.05)
            diverge_th: Limiar de divergência (padrão: 5x min loss)

        Returns:
            Tuple (optimal_lr, learning_rates, losses)
        """
        logger.info("🔍 Iniciando Learning Rate Finder...")
        logger.info(f"Range: {start_lr:.2e} → {end_lr:.2e} | Iterações: {num_iter}")

        # Reset
        self.model.load_state_dict(self.initial_state)
        self.model.to(self.device)
        self.model.train()

        # Preparar LRs (escala logarítmica)
        lr_schedule = np.logspace(
            np.log10(start_lr),
            np.log10(end_lr),
            num_iter
        )

        # Tracking
        self.learning_rates = []
        self.losses = []
        best_loss = float('inf')
        smoothed_loss = 0
        iteration = 0

        # Iterator infinito do dataloader
        train_iter = iter(train_loader)

        for lr in lr_schedule:
            # Atualizar LR
            for param_group in self.optimizer.param_groups:
                param_group['lr'] = lr

            # Obter batch
            try:
                batch = next(train_iter)
            except StopIteration:
                # Reiniciar iterator
                train_iter = iter(train_loader)
                batch = next(train_iter)

            # Forward pass
            loss = self._train_step(batch)

            # Suavizar loss (exponential moving average)
            if iteration == 0:
                smoothed_loss = loss
            else:
                smoothed_loss = smooth_f * loss + (1 - smooth_f) * smoothed_loss

            # Armazenar
            self.learning_rates.append(lr)
            self.losses.append(smoothed_loss)

            # Verificar divergência
            if smoothed_loss < best_loss:
                best_loss = smoothed_loss

            if smoothed_loss > diverge_th * best_loss:
                logger.warning(f"⚠️ Loss divergiu em LR={lr:.2e} (loss={smoothed_loss:.4f})")
                break

            iteration += 1

            if iteration % 10 == 0:
                logger.info(f"  Iter {iteration}/{num_iter} | LR={lr:.2e} | Loss={smoothed_loss:.4f}")

        # Encontrar LR ótimo
        optimal_lr = self._find_optimal_lr()

        logger.info(f"✅ Learning Rate Finder concluído!")
        logger.info(f"🎯 LR Ótimo Sugerido: {optimal_lr:.2e}")

        # Restaurar estado inicial do modelo
        self.model.load_state_dict(self.initial_state)

        return optimal_lr, self.learning_rates, self.losses

    def _train_step(self, batch) -> float:
        """Executa um passo de treino e retorna a loss"""
        # Assumindo batch no formato (images, labels) ou dict
        if isinstance(batch, dict):
            # Para datasets customizados que retornam dicts
            inputs = batch['image'].to(self.device) if 'image' in batch else batch['images'].to(self.device)

            # Labels podem ser preset_label, rating, ou sliders
            if 'preset_label' in batch:
                labels = batch['preset_label'].to(self.device)
            elif 'rating' in batch:
                labels = batch['rating'].to(self.device)
            elif 'sliders' in batch:
                labels = batch['sliders'].to(self.device)
            else:
                raise ValueError("Batch deve conter labels (preset_label, rating, ou sliders)")
        else:
            # Formato tradicional (inputs, labels)
            inputs, labels = batch
            inputs = inputs.to(self.device)
            labels = labels.to(self.device)

        # Forward pass
        self.optimizer.zero_grad()
        outputs = self.model(inputs)

        # Calcular loss
        loss = self.criterion(outputs, labels)

        # Backward pass
        loss.backward()
        self.optimizer.step()

        return loss.item()

    def _find_optimal_lr(self) -> float:
        """
        Encontra o LR ótimo baseado no gradiente da loss

        Método: LR onde a loss decresce mais rapidamente
        """
        if len(self.losses) < 10:
            logger.warning("⚠️ Poucas iterações para determinar LR ótimo. Retornando LR médio.")
            return self.learning_rates[len(self.learning_rates) // 2]

        # Calcular gradiente (derivada) da loss
        losses = np.array(self.losses)
        lrs = np.array(self.learning_rates)

        # Gradiente numérico
        gradients = np.gradient(losses)

        # Encontrar ponto de maior declínio (gradiente mais negativo)
        # Ignorar os primeiros 10% e últimos 10% (ruído e divergência)
        start_idx = len(gradients) // 10
        end_idx = len(gradients) - len(gradients) // 10

        if end_idx <= start_idx:
            end_idx = len(gradients) - 1

        min_gradient_idx = start_idx + np.argmin(gradients[start_idx:end_idx])

        # LR ótimo: um pouco antes do ponto de menor gradiente
        # Regra empírica: dividir por 10 ou usar 1/4 do caminho até o mínimo
        optimal_lr = lrs[min_gradient_idx] / 10

        # Garantir que está dentro do range testado
        optimal_lr = max(lrs[0], min(optimal_lr, lrs[-1]))

        return optimal_lr

    def plot(
        self,
        save_path: Optional[str] = None,
        skip_start: int = 10,
        skip_end: int = 5
    ) -> plt.Figure:
        """
        Plota curva de Loss vs Learning Rate

        Args:
            save_path: Caminho para salvar gráfico (opcional)
            skip_start: Número de pontos iniciais a ignorar
            skip_end: Número de pontos finais a ignorar

        Returns:
            Figura matplotlib
        """
        if not self.learning_rates or not self.losses:
            raise ValueError("Execute range_test() primeiro!")

        # Aplicar skip
        lrs = self.learning_rates[skip_start:-skip_end if skip_end > 0 else None]
        losses = self.losses[skip_start:-skip_end if skip_end > 0 else None]

        # Criar gráfico
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(lrs, losses, linewidth=2, color='#2E86AB')
        ax.set_xscale('log')
        ax.set_xlabel('Learning Rate (log scale)', fontsize=12)
        ax.set_ylabel('Loss', fontsize=12)
        ax.set_title('Learning Rate Finder', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)

        # Marcar LR ótimo
        optimal_lr = self._find_optimal_lr()
        optimal_idx = np.argmin(np.abs(np.array(self.learning_rates) - optimal_lr))
        optimal_loss = self.losses[optimal_idx]

        ax.axvline(optimal_lr, color='red', linestyle='--', linewidth=2, alpha=0.7)
        ax.scatter([optimal_lr], [optimal_loss], color='red', s=100, zorder=5, marker='o')
        ax.text(
            optimal_lr, optimal_loss,
            f'  Optimal LR\n  {optimal_lr:.2e}',
            fontsize=10,
            color='red',
            verticalalignment='bottom'
        )

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"💾 Gráfico salvo em: {save_path}")

        return fig

    def get_suggested_lr_range(self) -> Tuple[float, float]:
        """
        Retorna range de LR sugerido para Cyclical Learning Rate

        Returns:
            Tuple (min_lr, max_lr)
        """
        optimal_lr = self._find_optimal_lr()

        # Range sugerido: 1/10 do ótimo até o ótimo
        min_lr = optimal_lr / 10
        max_lr = optimal_lr

        return min_lr, max_lr


def find_optimal_lr(
    model: nn.Module,
    train_loader: torch.utils.data.DataLoader,
    criterion: nn.Module,
    device: str = "cpu",
    optimizer_class: type = torch.optim.Adam,
    **optimizer_kwargs
) -> Tuple[float, plt.Figure]:
    """
    Função helper para encontrar LR ótimo rapidamente

    Args:
        model: Modelo PyTorch
        train_loader: DataLoader de treino
        criterion: Função de perda
        device: Dispositivo
        optimizer_class: Classe do otimizador (padrão: Adam)
        **optimizer_kwargs: Kwargs para o otimizador

    Returns:
        Tuple (optimal_lr, figure)
    """
    # Criar otimizador temporário
    if 'lr' not in optimizer_kwargs:
        optimizer_kwargs['lr'] = 1e-7  # Será sobrescrito

    optimizer = optimizer_class(model.parameters(), **optimizer_kwargs)

    # Criar finder
    finder = LearningRateFinder(model, optimizer, criterion, device)

    # Range test
    optimal_lr, _, _ = finder.range_test(train_loader)

    # Plot
    fig = finder.plot()

    return optimal_lr, fig


if __name__ == "__main__":
    # Exemplo de uso
    print("Learning Rate Finder - Exemplo de Uso")
    print("=" * 60)
    print()
    print("from services.learning_rate_finder import find_optimal_lr")
    print()
    print("optimal_lr, fig = find_optimal_lr(")
    print("    model=my_model,")
    print("    train_loader=train_loader,")
    print("    criterion=nn.CrossEntropyLoss(),")
    print("    device='cuda'")
    print(")")
    print()
    print("print(f'Optimal LR: {optimal_lr:.2e}')")
    print("fig.savefig('lr_finder.png')")
