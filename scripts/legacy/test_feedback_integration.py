#!/usr/bin/env python3
"""
Script de teste para validar a integração completa do sistema de feedback.
Testa os endpoints FastAPI e verifica a estrutura da base de dados.

Uso:
    python test_feedback_integration.py
"""

import requests
import json
import sqlite3
from pathlib import Path
from datetime import datetime

# Configuração
SERVER_URL = "http://127.0.0.1:5678"
DB_PATH = Path(__file__).parent / "feedback.db"

def print_section(title):
    """Imprime cabeçalho de secção"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)

def test_server_health():
    """Testa se o servidor está online"""
    print_section("1. Teste de Conectividade")

    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Servidor está ONLINE")
            print(f"  Resposta: {response.json()}")
            return True
        else:
            print(f"✗ Servidor retornou status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Falha ao conectar ao servidor: {e}")
        return False

def test_implicit_feedback():
    """Testa endpoint /feedback/implicit"""
    print_section("2. Teste de Feedback Implícito")

    # Payload de teste (simula envio do Lightroom)
    payload = {
        "session_uuid": "test-uuid-implicit-001",
        "photo_hash": "ph_test123",
        "vector_before": [0.0] * 38,  # 38 zeros
        "vector_ai": [5.0] * 38,      # 38 valores a 5.0
        "vector_final": [10.0] * 38,  # 38 valores a 10.0 (editado)
        "model_version": "nn",
        "exif_data": {
            "iso": 400,
            "width": 6000,
            "height": 4000
        },
        "photo_category": None
    }

    try:
        response = requests.post(
            f"{SERVER_URL}/feedback/implicit",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            print("✓ Feedback implícito enviado com SUCESSO")
            result = response.json()
            print(f"  Session UUID: {result.get('session_uuid')}")
            print(f"  Timestamp: {result.get('timestamp')}")
            return True
        else:
            print(f"✗ Falha ao enviar feedback implícito: {response.status_code}")
            print(f"  Resposta: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Erro na requisição: {e}")
        return False

def test_explicit_feedback():
    """Testa endpoint /feedback/explicit"""
    print_section("3. Teste de Feedback Explícito")

    # Payload de teste
    payload = {
        "session_uuid": "test-uuid-explicit-001",
        "photo_hash": "ph_test456",
        "vector_current": [15.0] * 38,
        "rating": "good",
        "user_notes": "Teste automático de feedback explícito",
        "exif_data": {
            "iso": 800,
            "width": 4000,
            "height": 6000
        },
        "model_version": "nn"
    }

    try:
        response = requests.post(
            f"{SERVER_URL}/feedback/explicit",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            print("✓ Feedback explícito enviado com SUCESSO")
            result = response.json()
            print(f"  Session UUID: {result.get('session_uuid')}")
            print(f"  Rating: {result.get('rating')}")
            return True
        else:
            print(f"✗ Falha ao enviar feedback explícito: {response.status_code}")
            print(f"  Resposta: {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Erro na requisição: {e}")
        return False

def verify_database():
    """Verifica se os dados foram gravados na base de dados"""
    print_section("4. Verificação da Base de Dados")

    if not DB_PATH.exists():
        print(f"✗ Base de dados não encontrada: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Verificar tabela implicit_feedback
        cursor.execute("SELECT COUNT(*) FROM implicit_feedback WHERE session_uuid LIKE 'test-uuid-implicit%'")
        implicit_count = cursor.fetchone()[0]
        print(f"  Registos de teste em implicit_feedback: {implicit_count}")

        if implicit_count > 0:
            cursor.execute("""
                SELECT session_uuid, photo_hash, model_version, created_at
                FROM implicit_feedback
                WHERE session_uuid LIKE 'test-uuid-implicit%'
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            print(f"    Último registo:")
            print(f"      UUID: {row[0]}")
            print(f"      Hash: {row[1]}")
            print(f"      Modelo: {row[2]}")
            print(f"      Criado: {row[3]}")

        # Verificar tabela explicit_feedback
        cursor.execute("SELECT COUNT(*) FROM explicit_feedback WHERE session_uuid LIKE 'test-uuid-explicit%'")
        explicit_count = cursor.fetchone()[0]
        print(f"\n  Registos de teste em explicit_feedback: {explicit_count}")

        if explicit_count > 0:
            cursor.execute("""
                SELECT session_uuid, rating, user_notes, created_at
                FROM explicit_feedback
                WHERE session_uuid LIKE 'test-uuid-explicit%'
                ORDER BY created_at DESC LIMIT 1
            """)
            row = cursor.fetchone()
            print(f"    Último registo:")
            print(f"      UUID: {row[0]}")
            print(f"      Rating: {row[1]}")
            print(f"      Notas: {row[2]}")
            print(f"      Criado: {row[3]}")

        conn.close()

        if implicit_count > 0 and explicit_count > 0:
            print("\n✓ Base de dados contém dados de AMBOS os tipos de feedback")
            return True
        else:
            print("\n⚠ Alguns tipos de feedback não foram encontrados na base de dados")
            return False

    except sqlite3.Error as e:
        print(f"✗ Erro ao aceder à base de dados: {e}")
        return False

def test_granular_feedback():
    """Testa endpoint /feedback/granular (opcional)"""
    print_section("5. Teste de Feedback Granular (Opcional)")

    payload = {
        "session_uuid": "test-uuid-granular-001",
        "photo_hash": "ph_test789",
        "slider_name": "exposure",
        "value_before": 0.0,
        "value_after": 2.5,
        "user_accepted": True,
        "model_version": "nn"
    }

    try:
        response = requests.post(
            f"{SERVER_URL}/feedback/granular",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            print("✓ Feedback granular enviado com SUCESSO")
            result = response.json()
            print(f"  Slider: {result.get('slider_name')}")
            print(f"  Aceite: {result.get('user_accepted')}")
            return True
        else:
            print(f"⚠ Endpoint granular não disponível ou falhou: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"⚠ Endpoint granular não disponível: {e}")
        return False

def cleanup_test_data():
    """Remove dados de teste da base de dados"""
    print_section("6. Limpeza de Dados de Teste")

    if not DB_PATH.exists():
        print("  Base de dados não encontrada, nada a limpar")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Remover registos de teste
        cursor.execute("DELETE FROM implicit_feedback WHERE session_uuid LIKE 'test-uuid-%'")
        implicit_deleted = cursor.rowcount

        cursor.execute("DELETE FROM explicit_feedback WHERE session_uuid LIKE 'test-uuid-%'")
        explicit_deleted = cursor.rowcount

        cursor.execute("DELETE FROM granular_feedback WHERE session_uuid LIKE 'test-uuid-%'")
        granular_deleted = cursor.rowcount

        conn.commit()
        conn.close()

        print(f"  Removidos:")
        print(f"    - {implicit_deleted} registos de implicit_feedback")
        print(f"    - {explicit_deleted} registos de explicit_feedback")
        print(f"    - {granular_deleted} registos de granular_feedback")
        print("✓ Limpeza concluída")

    except sqlite3.Error as e:
        print(f"✗ Erro ao limpar dados de teste: {e}")

def main():
    """Executa todos os testes"""
    print("\n" + "█"*70)
    print("  TESTE DE INTEGRAÇÃO - NSP PLUGIN FEEDBACK SYSTEM")
    print("█"*70)
    print(f"\nData/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Servidor: {SERVER_URL}")
    print(f"Base de Dados: {DB_PATH}")

    # Executar testes
    results = []

    results.append(("Conectividade", test_server_health()))

    if results[0][1]:  # Só continua se servidor estiver online
        results.append(("Feedback Implícito", test_implicit_feedback()))
        results.append(("Feedback Explícito", test_explicit_feedback()))
        results.append(("Feedback Granular", test_granular_feedback()))
        results.append(("Verificação DB", verify_database()))

    # Sumário
    print_section("SUMÁRIO DE RESULTADOS")

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status:10} {test_name}")

    print(f"\n  Total: {passed}/{total} testes passaram")

    # Perguntar sobre limpeza
    if any(result for _, result in results):
        print("\n" + "-"*70)
        response = input("Deseja remover os dados de teste da base de dados? (s/N): ")
        if response.lower() == 's':
            cleanup_test_data()

    print("\n" + "█"*70)
    print("  FIM DOS TESTES")
    print("█"*70 + "\n")

    return passed == total

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
