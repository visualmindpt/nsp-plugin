# -*- coding: utf-8 -*-
"""
Training Progress Tracker - Sistema de tracking de progresso para treino
Fornece feedback visual detalhado durante o treino
"""

import sys
import time
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
import json

# Adicionar root ao path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))


class TrainingProgressTracker:
    """Tracker de progresso de treino com estimativas de tempo"""

    def __init__(self, total_epochs: int, phase_name: str = "Training"):
        self.total_epochs = total_epochs
        self.phase_name = phase_name
        self.current_epoch = 0
        self.start_time = None
        self.epoch_start_time = None
        self.epoch_times = []
        self.best_loss = float('inf')
        self.best_epoch = 0
        self.metrics_history = []

    def start(self):
        """Inicia o tracking"""
        self.start_time = time.time()
        print(f"\n{'='*60}")
        print(f"🚀 Iniciando {self.phase_name}")
        print(f"   Total de epochs: {self.total_epochs}")
        print(f"   Início: {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}\n")

    def start_epoch(self, epoch: int):
        """Inicia tracking de uma epoch"""
        self.current_epoch = epoch
        self.epoch_start_time = time.time()

    def end_epoch(self, metrics: Dict[str, float]):
        """Finaliza tracking de uma epoch e mostra progresso"""
        if self.epoch_start_time is None:
            return

        epoch_time = time.time() - self.epoch_start_time
        self.epoch_times.append(epoch_time)
        self.metrics_history.append({
            'epoch': self.current_epoch,
            'time': epoch_time,
            **metrics
        })

        # Calcular estimativas
        avg_epoch_time = sum(self.epoch_times) / len(self.epoch_times)
        remaining_epochs = self.total_epochs - self.current_epoch
        estimated_remaining = avg_epoch_time * remaining_epochs
        elapsed_total = time.time() - self.start_time

        # Atualizar best loss
        current_loss = metrics.get('val_loss', metrics.get('loss', float('inf')))
        if current_loss < self.best_loss:
            self.best_loss = current_loss
            self.best_epoch = self.current_epoch
            improved = "🎯"
        else:
            improved = ""

        # Progress bar
        progress = (self.current_epoch / self.total_epochs) * 100
        bar_length = 30
        filled = int(bar_length * self.current_epoch / self.total_epochs)
        bar = '█' * filled + '░' * (bar_length - filled)

        # Formatar métricas
        metrics_str = " | ".join([
            f"{k}: {v:.4f}" if isinstance(v, float) else f"{k}: {v}"
            for k, v in metrics.items()
        ])

        print(f"Epoch {self.current_epoch:3d}/{self.total_epochs} "
              f"[{bar}] {progress:5.1f}% {improved}")
        print(f"  ⏱️  Tempo: {self._format_time(epoch_time)} "
              f"(avg: {self._format_time(avg_epoch_time)})")
        print(f"  📊 {metrics_str}")
        print(f"  ⏳ Restante: ~{self._format_time(estimated_remaining)} "
              f"| Total: {self._format_time(elapsed_total)}")
        print()

    def finish(self, final_metrics: Optional[Dict[str, Any]] = None):
        """Finaliza tracking e mostra resumo"""
        total_time = time.time() - self.start_time

        print(f"\n{'='*60}")
        print(f"✅ {self.phase_name} CONCLUÍDO")
        print(f"{'='*60}")
        print(f"⏱️  Tempo total: {self._format_time(total_time)}")
        print(f"📈 Melhor epoch: {self.best_epoch} (loss: {self.best_loss:.4f})")

        if self.epoch_times:
            print(f"⚡ Tempo médio por epoch: {self._format_time(sum(self.epoch_times) / len(self.epoch_times))}")
            print(f"🚀 Epoch mais rápida: {self._format_time(min(self.epoch_times))}")
            print(f"🐌 Epoch mais lenta: {self._format_time(max(self.epoch_times))}")

        if final_metrics:
            print(f"\n📊 Métricas finais:")
            for key, value in final_metrics.items():
                if isinstance(value, float):
                    print(f"   {key}: {value:.4f}")
                else:
                    print(f"   {key}: {value}")

        print(f"{'='*60}\n")

    def save_history(self, output_path: Path):
        """Salva histórico de métricas"""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        history = {
            'phase': self.phase_name,
            'total_epochs': self.total_epochs,
            'total_time': time.time() - self.start_time if self.start_time else 0,
            'best_epoch': self.best_epoch,
            'best_loss': self.best_loss,
            'metrics_history': self.metrics_history
        }

        with open(output_path, 'w') as f:
            json.dump(history, f, indent=2)

        print(f"💾 Histórico salvo em: {output_path}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Formata segundos em formato legível"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"


class MultiPhaseTracker:
    """Tracker para múltiplas fases de treino"""

    def __init__(self, phases: Dict[str, int]):
        """
        Args:
            phases: Dict com nome da fase -> número de epochs
                    Ex: {'Classifier': 50, 'Refiner': 100}
        """
        self.phases = phases
        self.current_phase = None
        self.phase_trackers = {}
        self.global_start_time = None

    def start(self):
        """Inicia tracking global"""
        self.global_start_time = time.time()
        total_epochs = sum(self.phases.values())
        print(f"\n{'='*70}")
        print(f"🎯 INICIANDO TREINO MULTI-FASE")
        print(f"{'='*70}")
        print(f"Fases:")
        for phase, epochs in self.phases.items():
            print(f"  • {phase}: {epochs} epochs")
        print(f"\n📊 Total de epochs: {total_epochs}")
        print(f"🕐 Início: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

    def start_phase(self, phase_name: str) -> TrainingProgressTracker:
        """Inicia uma nova fase"""
        if phase_name not in self.phases:
            raise ValueError(f"Fase desconhecida: {phase_name}")

        self.current_phase = phase_name
        tracker = TrainingProgressTracker(
            total_epochs=self.phases[phase_name],
            phase_name=phase_name
        )
        self.phase_trackers[phase_name] = tracker
        tracker.start()
        return tracker

    def finish(self):
        """Finaliza tracking global e mostra resumo geral"""
        total_time = time.time() - self.global_start_time

        print(f"\n{'='*70}")
        print(f"🎉 TREINO COMPLETO - TODAS AS FASES CONCLUÍDAS")
        print(f"{'='*70}")
        print(f"⏱️  Tempo total: {TrainingProgressTracker._format_time(total_time)}")
        print(f"🕐 Término: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n📊 Resumo por fase:")

        for phase_name, tracker in self.phase_trackers.items():
            print(f"\n  {phase_name}:")
            print(f"    • Melhor epoch: {tracker.best_epoch}")
            print(f"    • Melhor loss: {tracker.best_loss:.4f}")
            if tracker.epoch_times:
                avg_time = sum(tracker.epoch_times) / len(tracker.epoch_times)
                print(f"    • Tempo médio/epoch: {TrainingProgressTracker._format_time(avg_time)}")

        print(f"\n{'='*70}\n")


# Exemplo de uso
if __name__ == "__main__":
    # Exemplo 1: Fase única
    print("Exemplo 1: Treino de fase única\n")
    tracker = TrainingProgressTracker(total_epochs=10, phase_name="Classifier Training")
    tracker.start()

    for epoch in range(1, 11):
        tracker.start_epoch(epoch)
        time.sleep(0.5)  # Simula treino
        metrics = {
            'loss': 1.0 / epoch,
            'val_loss': 1.2 / epoch,
            'accuracy': 0.5 + (epoch / 20)
        }
        tracker.end_epoch(metrics)

    tracker.finish({'final_accuracy': 0.95})
    tracker.save_history(Path('logs/training_history.json'))

    print("\n" + "="*70 + "\n")

    # Exemplo 2: Multi-fase
    print("Exemplo 2: Treino multi-fase\n")
    multi_tracker = MultiPhaseTracker({
        'Classifier': 5,
        'Refiner': 5
    })
    multi_tracker.start()

    for phase in ['Classifier', 'Refiner']:
        phase_tracker = multi_tracker.start_phase(phase)
        for epoch in range(1, multi_tracker.phases[phase] + 1):
            phase_tracker.start_epoch(epoch)
            time.sleep(0.3)
            metrics = {'loss': 1.0 / (epoch + 5), 'val_loss': 1.1 / (epoch + 5)}
            phase_tracker.end_epoch(metrics)
        phase_tracker.finish()

    multi_tracker.finish()
