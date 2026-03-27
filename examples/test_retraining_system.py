"""
examples/test_retraining_system.py

Script de teste para o sistema de retreino automático.
Demonstra todo o fluxo: verificar readiness → trigger → monitorizar → validar.
"""

import json
import time
from pathlib import Path

import requests

# Configuração
BASE_URL = "http://localhost:5678"
TRAINING_API = f"{BASE_URL}/training"


def print_section(title: str):
    """Imprime seção formatada."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def check_server_health():
    """Verifica se servidor está a responder."""
    print_section("1. VERIFICAR SAÚDE DO SERVIDOR")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        response.raise_for_status()

        data = response.json()
        print(f"✓ Servidor está online")
        print(f"  Status: {data['status']}")
        print(f"  Modelos disponíveis: {data['models']}")

        return True

    except Exception as e:
        print(f"✗ Erro ao conectar ao servidor: {e}")
        print(f"  Certifica-te que o servidor está a correr em {BASE_URL}")
        return False


def check_readiness():
    """Verifica se sistema está pronto para retreino."""
    print_section("2. VERIFICAR READINESS")

    try:
        response = requests.get(f"{TRAINING_API}/ready", timeout=5)
        response.raise_for_status()

        data = response.json()

        print(f"Ready: {data['ready']}")
        print(f"Reason: {data['reason']}")
        print("\nMétricas:")

        metrics = data['metrics']
        print(f"  - Feedback validado: {metrics.get('validated_count', 0)}")
        print(f"  - Qualidade média: {metrics.get('avg_quality', 0):.3f}")
        print(f"  - Outliers: {metrics.get('outlier_percentage', 0):.1%}")
        print(f"  - Drift score: {metrics.get('drift_score', 0):.3f}")
        print(f"  - Cooldown restante: {metrics.get('cooldown_remaining_hours', 0):.1f}h")

        return data['ready']

    except Exception as e:
        print(f"✗ Erro ao verificar readiness: {e}")
        return False


def trigger_retraining(force: bool = False):
    """Dispara retreino."""
    print_section("3. DISPARAR RETREINO")

    payload = {
        "training_type": "incremental",
        "min_feedback_quality": 0.7,
        "use_feedback_only": False,
        "force": force,
        "notes": "Teste automático via test_retraining_system.py"
    }

    print(f"Configuração:")
    print(f"  - Tipo: {payload['training_type']}")
    print(f"  - Qualidade mínima: {payload['min_feedback_quality']}")
    print(f"  - Usar apenas feedback: {payload['use_feedback_only']}")
    print(f"  - Forçar: {payload['force']}")

    try:
        response = requests.post(
            f"{TRAINING_API}/trigger",
            json=payload,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()

        print(f"\n✓ Retreino iniciado!")
        print(f"  Run ID: {data['run_id']}")
        print(f"  Status: {data['status']}")

        return data['run_id']

    except requests.exceptions.HTTPError as e:
        print(f"✗ Erro HTTP ao disparar retreino:")
        print(f"  Status: {e.response.status_code}")
        print(f"  Mensagem: {e.response.json().get('detail', 'Erro desconhecido')}")
        return None

    except Exception as e:
        print(f"✗ Erro ao disparar retreino: {e}")
        return None


def monitor_retraining(run_id: str, poll_interval: int = 5):
    """Monitoriza progresso do retreino em tempo real."""
    print_section("4. MONITORIZAR PROGRESSO")

    print(f"Run ID: {run_id}")
    print(f"Poll interval: {poll_interval}s")
    print("\nMonitorização em tempo real (Ctrl+C para parar):\n")

    try:
        previous_status = None

        while True:
            response = requests.get(
                f"{TRAINING_API}/status/{run_id}",
                timeout=5
            )
            response.raise_for_status()

            data = response.json()

            status = data['status']
            progress = data['progress']

            # Mostrar apenas quando status mudar ou progresso significativo
            if status != previous_status or progress > 0.0:
                timestamp = time.strftime("%H:%M:%S")

                print(f"[{timestamp}] Status: {status:12} | Progress: {progress:5.1%}", end="")

                if data.get('current_epoch') is not None:
                    print(f" | Epoch: {data['current_epoch']}/{data['total_epochs']}", end="")

                if data.get('validation_loss') is not None:
                    print(f" | Val Loss: {data['validation_loss']:.4f}", end="")

                print(f" | {data['message']}")

                previous_status = status

            # Verificar se terminou
            if status in ['completed', 'failed']:
                print(f"\n{'✓' if status == 'completed' else '✗'} Retreino {status}")

                if data.get('samples_used'):
                    print(f"  Samples usados: {data['samples_used']}")

                if data.get('validation_loss'):
                    print(f"  Validation loss: {data['validation_loss']:.4f}")

                return status == 'completed'

            time.sleep(poll_interval)

    except KeyboardInterrupt:
        print("\n\n⚠ Monitorização interrompida (retreino continua em background)")
        return None

    except Exception as e:
        print(f"\n✗ Erro ao monitorizar: {e}")
        return None


def view_training_stats():
    """Mostra estatísticas do sistema."""
    print_section("5. ESTATÍSTICAS DO SISTEMA")

    try:
        response = requests.get(f"{TRAINING_API}/stats", timeout=5)
        response.raise_for_status()

        data = response.json()

        # Feedback
        print("Feedback:")
        feedback = data['feedback']
        print(f"  - Total: {feedback['total']}")
        print(f"  - Validado: {feedback['validated']}")
        print(f"  - Outliers: {feedback['outliers']}")
        print(f"  - Qualidade média: {feedback['avg_quality']:.3f}")

        # Último retreino
        print("\nÚltimo Retreino:")
        last_retrain = data.get('last_retrain')
        if last_retrain:
            print(f"  - ID: {last_retrain['id']}")
            print(f"  - Data: {last_retrain['started_at']}")
            print(f"  - Duração: {last_retrain['duration_seconds']:.1f}s")
            print(f"  - Feedback usado: {last_retrain['feedback_count']}")
            print(f"  - Validation MAE: {last_retrain['validation_mae']:.4f}")
        else:
            print("  (Nenhum retreino executado)")

        # Modelos
        print("\nModelos:")
        models = data['models']
        print(f"  - Versão atual: {models['current_version']}")
        print(f"  - Backups disponíveis: {models['available_backups']}")

        return True

    except Exception as e:
        print(f"✗ Erro ao obter estatísticas: {e}")
        return False


def view_training_history(limit: int = 5):
    """Mostra histórico de retreinos."""
    print_section("6. HISTÓRICO DE RETREINOS")

    try:
        response = requests.get(
            f"{TRAINING_API}/history",
            params={'limit': limit},
            timeout=5
        )
        response.raise_for_status()

        data = response.json()
        history = data['history']

        if not history:
            print("Nenhum retreino no histórico")
            return

        print(f"Últimos {len(history)} retreinos:\n")

        for i, item in enumerate(history, 1):
            status_icon = "✓" if item['status'] == 'success' else "✗"

            print(f"{i}. [{status_icon}] ID: {item['id']}")
            print(f"   Data: {item['started_at']}")
            print(f"   Duração: {item['duration_seconds']:.1f}s")
            print(f"   Trigger: {item['trigger_type']}")
            print(f"   Feedback: {item['feedback_count']}")
            print(f"   Status: {item['status']}")
            print()

    except Exception as e:
        print(f"✗ Erro ao obter histórico: {e}")


def list_model_versions():
    """Lista versões disponíveis."""
    print_section("7. VERSÕES DISPONÍVEIS")

    try:
        response = requests.get(f"{TRAINING_API}/model/versions", timeout=5)
        response.raise_for_status()

        data = response.json()
        versions = data['versions']

        if not versions:
            print("Nenhum backup disponível")
            return

        print(f"Total: {len(versions)} backups\n")

        for i, version in enumerate(versions[:5], 1):
            print(f"{i}. {version['name']}")
            print(f"   Data: {version['backup_date']}")
            print(f"   Tamanho: {version['size_mb']} MB")
            print()

    except Exception as e:
        print(f"✗ Erro ao listar versões: {e}")


def main():
    """Fluxo principal de teste."""
    print("\n" + "█" * 80)
    print("  TESTE DO SISTEMA DE RETREINO AUTOMÁTICO")
    print("█" * 80)

    # 1. Verificar servidor
    if not check_server_health():
        print("\n⚠ Servidor não está disponível. Abortando teste.")
        return

    # 2. Verificar readiness
    ready = check_readiness()

    # 3. Perguntar ao utilizador
    print_section("DECISÃO")

    if not ready:
        print("⚠ Sistema NÃO está pronto para retreino.")
        print("\nOpções:")
        print("  1. Abortar teste")
        print("  2. Forçar retreino (ignorar thresholds)")

        choice = input("\nEscolha (1 ou 2): ").strip()

        if choice == "1":
            print("\nTeste abortado pelo utilizador.")
            print("\nPara retreino bem-sucedido, é necessário:")
            print("  - Pelo menos 50 feedbacks validados")
            print("  - Qualidade média ≥ 0.7")
            print("  - Outliers ≤ 15%")
            print("  - Cooldown de 12h passou")
            return

        elif choice == "2":
            print("\n⚠ AVISO: Forçar retreino pode resultar em modelo de baixa qualidade")
            confirm = input("Tens a certeza? (yes/no): ").strip().lower()

            if confirm != "yes":
                print("\nTeste abortado.")
                return

            force = True
        else:
            print("\nEscolha inválida. Teste abortado.")
            return
    else:
        print("✓ Sistema ESTÁ pronto para retreino!")

        choice = input("\nIniciar retreino? (yes/no): ").strip().lower()

        if choice != "yes":
            print("\nTeste abortado pelo utilizador.")
            return

        force = False

    # 4. Disparar retreino
    run_id = trigger_retraining(force=force)

    if not run_id:
        print("\n⚠ Falha ao disparar retreino. Abortando.")
        return

    # 5. Monitorizar
    success = monitor_retraining(run_id, poll_interval=5)

    if success is None:
        print("\n⚠ Monitorização interrompida.")
        print(f"Para continuar a monitorizar:")
        print(f"  curl {TRAINING_API}/status/{run_id}")
        return

    # 6. Mostrar estatísticas finais
    if success:
        view_training_stats()
        view_training_history(limit=3)
        list_model_versions()

        print_section("CONCLUSÃO")
        print("✓ Retreino concluído com SUCESSO!")
        print("\nO novo modelo foi deployado para produção.")
        print("Backups do modelo anterior foram criados automaticamente.")
        print("\nPróximos passos:")
        print("  1. Testar previsões com novo modelo: POST /predict")
        print("  2. Monitorizar feedback dos utilizadores")
        print("  3. Se necessário, rollback: POST /training/rollback/<version>")

    else:
        print_section("CONCLUSÃO")
        print("✗ Retreino FALHOU")
        print("\nVerificar logs do servidor para detalhes:")
        print("  - Possíveis causas: modelo não melhorou, erro de validação, etc.")
        print("  - Modelo anterior continua em produção (não foi alterado)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Teste interrompido pelo utilizador")
    except Exception as e:
        print(f"\n✗ Erro inesperado: {e}")
        import traceback
        traceback.print_exc()
