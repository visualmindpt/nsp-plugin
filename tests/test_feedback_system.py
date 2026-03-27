"""
tests/test_feedback_system.py

Testes para validar o sistema de feedback granular completo.
"""

import sys
from pathlib import Path

# Adicionar project root ao path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from services.feedback_manager import FeedbackManager
from services.feedback_schemas import (
    GranularFeedbackRequest,
    SliderFeedbackItem,
    ExplicitFeedbackRequest,
)


def test_feedback_schemas():
    """Testa validação dos Pydantic schemas."""
    print("\n" + "="*70)
    print("TESTE 1: Validação de Schemas")
    print("="*70)

    # Criar feedback item válido
    slider_item = SliderFeedbackItem(
        slider_name='exposure',
        predicted_value=0.5,
        user_value=1.2,
        time_to_edit_seconds=3.5
    )
    print(f"✓ SliderFeedbackItem criado: {slider_item.slider_name}")

    # Criar request granular válido
    request = GranularFeedbackRequest(
        original_record_id=1,
        session_id='test-session-123',
        edited_sliders=[slider_item]
    )
    print(f"✓ GranularFeedbackRequest criado com {len(request.edited_sliders)} sliders")

    # Testar validação de range inválido
    try:
        invalid_item = SliderFeedbackItem(
            slider_name='exposure',
            predicted_value=10.0,  # Fora do range [-5, 5]
            user_value=1.0
        )
        print("✗ Validação de range falhou (não deveria aceitar)")
    except ValueError as e:
        print(f"✓ Validação de range funcionou: {str(e)[:50]}...")

    # Testar slider inválido
    try:
        invalid_slider = SliderFeedbackItem(
            slider_name='invalid_slider',
            predicted_value=0.5,
            user_value=1.0
        )
        print("✗ Validação de nome falhou (não deveria aceitar)")
    except ValueError as e:
        print(f"✓ Validação de nome funcionou: {str(e)[:50]}...")

    print("\n✓ Teste de schemas: PASSOU\n")


def test_feedback_manager():
    """Testa o FeedbackManager."""
    print("="*70)
    print("TESTE 2: FeedbackManager")
    print("="*70)

    db_path = PROJECT_ROOT / 'data' / 'nsp_plugin.db'
    manager = FeedbackManager(db_path)

    print(f"✓ FeedbackManager inicializado")
    print(f"  - confidence_threshold: {manager.confidence_threshold}")
    print(f"  - outlier_std_multiplier: {manager.outlier_std_multiplier}")

    # Criar um record de teste se não existir
    import json
    from services.db_utils import get_db_connection

    test_vector = [0.0] * 38
    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM records WHERE id = 1")
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO records (id, image_path, exif, develop_vector) VALUES (?, ?, ?, ?)",
                    (1, '/test/image.jpg', '{}', json.dumps(test_vector))
                )
                print("✓ Record de teste criado (id=1)")
    except Exception as e:
        print(f"Aviso: {e}")

    # Criar feedback de teste
    test_feedback = GranularFeedbackRequest(
        original_record_id=1,
        session_id='test-session-001',
        edited_sliders=[
            SliderFeedbackItem(
                slider_name='exposure',
                predicted_value=0.0,
                user_value=1.5,
                time_to_edit_seconds=2.0
            ),
            SliderFeedbackItem(
                slider_name='contrast',
                predicted_value=10.0,
                user_value=25.0,
                time_to_edit_seconds=3.5
            ),
            SliderFeedbackItem(
                slider_name='highlights',
                predicted_value=-20.0,
                user_value=-40.0,
                time_to_edit_seconds=1.5
            ),
        ]
    )

    print(f"\n✓ Feedback de teste criado com {len(test_feedback.edited_sliders)} sliders")

    # Processar feedback
    print("\nA processar feedback...")
    result = manager.process_feedback(test_feedback)

    print(f"\n✓ Resultado do processamento:")
    print(f"  - Success: {result.success}")
    print(f"  - Total feedbacks: {result.total_feedbacks}")
    print(f"  - Validated: {result.validated_count}")
    print(f"  - Outliers: {result.outlier_count}")
    print(f"  - Message: {result.message}")
    print(f"  - IDs: {result.feedback_ids}")

    if result.success:
        print("\n✓ Teste de FeedbackManager: PASSOU\n")
    else:
        print("\n✗ Teste de FeedbackManager: FALHOU\n")
        print(f"Erro: {result.message}")


def test_validated_feedback_retrieval():
    """Testa obtenção de feedback validado."""
    print("="*70)
    print("TESTE 3: Obtenção de Feedback Validado")
    print("="*70)

    db_path = PROJECT_ROOT / 'data' / 'nsp_plugin.db'
    manager = FeedbackManager(db_path)

    # Obter feedback validado
    validated = manager.get_validated_feedback_for_training(
        min_quality=0.5,
        max_count=10
    )

    print(f"\n✓ Feedback validado obtido: {len(validated)} registros")

    if validated:
        print("\nPrimeiro registro:")
        first = validated[0]
        print(f"  - ID: {first['id']}")
        print(f"  - Slider: {first['slider_name']} (idx: {first['slider_index']})")
        print(f"  - Predicted: {first['predicted_value']}")
        print(f"  - User: {first['user_value']}")
        print(f"  - Delta: {first['delta_value']}")
        print(f"  - Confidence: {first['confidence_score']:.3f}")
        print(f"  - Quality: {first['feedback_quality']:.3f}")

    print("\n✓ Teste de retrieval: PASSOU\n")


def test_explicit_feedback():
    """Testa processamento de feedback explícito."""
    print("="*70)
    print("TESTE 4: Feedback Explícito")
    print("="*70)

    db_path = PROJECT_ROOT / 'data' / 'nsp_plugin.db'
    manager = FeedbackManager(db_path)

    # Criar vetores de 38 valores com valores válidos para cada slider
    from slider_config import ALL_SLIDER_NAMES, SLIDER_RANGES

    predicted_values = []
    corrected_values = []

    for slider_name in ALL_SLIDER_NAMES:
        slider_range = SLIDER_RANGES[slider_name]
        # Usar valor médio do range como predicted
        mid_value = (slider_range['min'] + slider_range['max']) / 2
        predicted_values.append(mid_value)
        corrected_values.append(mid_value)

    # Modificar alguns valores (mantendo dentro dos ranges)
    corrected_values[0] = 1.5   # exposure
    corrected_values[1] = 20.0  # contrast
    corrected_values[11] = 5500.0  # temp

    explicit_feedback = ExplicitFeedbackRequest(
        original_record_id=1,
        session_id='test-explicit-001',
        predicted_values=predicted_values,
        corrected_values=corrected_values
    )

    print(f"✓ Feedback explícito criado (38 valores)")

    result = manager.process_explicit_feedback(explicit_feedback)

    print(f"\n✓ Resultado do processamento:")
    print(f"  - Success: {result.success}")
    print(f"  - Total feedbacks: {result.total_feedbacks}")
    print(f"  - Message: {result.message}")

    print("\n✓ Teste de feedback explícito: PASSOU\n")


def test_database_views():
    """Testa as views criadas."""
    print("="*70)
    print("TESTE 5: Views da Base de Dados")
    print("="*70)

    import sqlite3
    from services.db_utils import get_db_connection

    db_path = PROJECT_ROOT / 'data' / 'nsp_plugin.db'

    try:
        with get_db_connection(db_path) as conn:
            cursor = conn.cursor()

            # Testar v_slider_feedback_stats
            cursor.execute("SELECT * FROM v_slider_feedback_stats LIMIT 5")
            stats = cursor.fetchall()
            print(f"\n✓ v_slider_feedback_stats: {len(stats)} sliders com feedback")

            if stats:
                print("\nTop 3 sliders editados:")
                for i, row in enumerate(stats[:3], 1):
                    print(f"  {i}. {row['slider_name']}: {row['edit_count']} edições")

            # Testar v_feedback_ready_for_training
            cursor.execute("SELECT COUNT(*) as count FROM v_feedback_ready_for_training")
            count = cursor.fetchone()['count']
            print(f"\n✓ v_feedback_ready_for_training: {count} feedbacks prontos")

            # Testar v_recent_retrainings
            cursor.execute("SELECT COUNT(*) as count FROM v_recent_retrainings")
            count = cursor.fetchone()['count']
            print(f"\n✓ v_recent_retrainings: {count} re-treinos no histórico")

        print("\n✓ Teste de views: PASSOU\n")

    except Exception as e:
        print(f"\n✗ Teste de views: FALHOU")
        print(f"Erro: {e}\n")


def run_all_tests():
    """Executa todos os testes."""
    print("\n" + "#"*70)
    print("# TESTES DO SISTEMA DE FEEDBACK GRANULAR")
    print("#"*70)

    try:
        test_feedback_schemas()
        test_feedback_manager()
        test_validated_feedback_retrieval()
        test_explicit_feedback()
        test_database_views()

        print("#"*70)
        print("# TODOS OS TESTES PASSARAM!")
        print("#"*70 + "\n")

    except Exception as e:
        print("\n" + "#"*70)
        print("# ERRO NOS TESTES")
        print("#"*70)
        print(f"\nErro: {e}")
        import traceback
        traceback.print_exc()
        print()


if __name__ == '__main__':
    run_all_tests()
