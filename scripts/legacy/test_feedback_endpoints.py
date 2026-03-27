#!/usr/bin/env python3
"""
test_feedback_endpoints.py

Script de teste rápido para validar os novos endpoints de feedback granular.
Testa que os endpoints respondem correctamente e validam dados.
"""

import requests
import json
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:5678"

def test_endpoint(method: str, path: str, data: Dict[str, Any] = None, params: Dict[str, Any] = None) -> None:
    """Testa um endpoint e mostra o resultado."""
    url = f"{BASE_URL}{path}"

    try:
        if method == "GET":
            response = requests.get(url, params=params, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            print(f"❌ Método {method} não suportado")
            return

        print(f"\n{'='*80}")
        print(f"{method} {path}")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print(f"✅ Sucesso!")
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}...")
        else:
            print(f"❌ Erro!")
            print(f"Response: {response.text[:500]}")

    except requests.exceptions.ConnectionError:
        print(f"❌ Servidor não está a correr em {BASE_URL}")
        print(f"   Execute: python -m services.server")
    except Exception as e:
        print(f"❌ Erro: {e}")


def main():
    """Executa testes nos novos endpoints."""

    print("=" * 80)
    print("TESTE DE ENDPOINTS DE FEEDBACK GRANULAR")
    print("=" * 80)

    # Teste 1: GET /feedback/stats (sem dados, deve funcionar mesmo sem feedback)
    print("\n📊 Teste 1: GET /feedback/stats")
    test_endpoint("GET", "/feedback/stats", params={"days": 7})

    # Teste 2: GET /feedback/quality-metrics
    print("\n📈 Teste 2: GET /feedback/quality-metrics")
    test_endpoint("GET", "/feedback/quality-metrics", params={"limit": 5})

    # Teste 3: POST /feedback/granular (deve falhar com dados inválidos)
    print("\n🔍 Teste 3: POST /feedback/granular (payload inválido - esperado erro)")
    test_endpoint("POST", "/feedback/granular", data={
        "original_record_id": 999999,  # Provavelmente não existe
        "session_id": "test-session-001",
        "edited_sliders": []  # Lista vazia deve falhar validação
    })

    # Teste 4: POST /feedback/granular (payload válido estruturalmente)
    print("\n✅ Teste 4: POST /feedback/granular (estrutura válida)")
    test_endpoint("POST", "/feedback/granular", data={
        "original_record_id": 1,  # Assumindo que existe record_id=1
        "session_id": "test-session-002",
        "edited_sliders": [
            {
                "slider_name": "Exposure2012",
                "predicted_value": 0.5,
                "user_value": 1.2,
                "time_to_edit_seconds": 3.5
            },
            {
                "slider_name": "Contrast2012",
                "predicted_value": 10.0,
                "user_value": 15.0,
                "time_to_edit_seconds": 2.0
            }
        ]
    })

    # Teste 5: POST /feedback/implicit
    print("\n💭 Teste 5: POST /feedback/implicit")
    test_endpoint("POST", "/feedback/implicit", data={
        "original_record_id": 1,
        "session_id": "test-session-003",
        "predicted_values": [0.0] * 38,  # 38 zeros (valores válidos)
        "time_to_accept_seconds": 2.5
    })

    # Teste 6: POST /feedback/explicit
    print("\n📝 Teste 6: POST /feedback/explicit")
    test_endpoint("POST", "/feedback/explicit", data={
        "original_record_id": 1,
        "session_id": "test-session-004",
        "predicted_values": [0.0] * 38,
        "corrected_values": [0.0] * 38  # Sem mudanças (todos aceites)
    })

    # Teste 7: Validação de slider_name inválido
    print("\n❌ Teste 7: POST /feedback/granular (slider_name inválido - esperado erro)")
    test_endpoint("POST", "/feedback/granular", data={
        "original_record_id": 1,
        "session_id": "test-session-005",
        "edited_sliders": [
            {
                "slider_name": "InvalidSliderName123",  # Nome inválido
                "predicted_value": 0.5,
                "user_value": 1.2
            }
        ]
    })

    print("\n" + "=" * 80)
    print("TESTES CONCLUÍDOS")
    print("=" * 80)
    print("\nNotas:")
    print("- Alguns testes podem falhar se não houver records na base de dados")
    print("- Erros de validação (422) são esperados em alguns casos")
    print("- Se o servidor não estiver a correr, todos os testes falharão")
    print("\nPara iniciar o servidor:")
    print("  python -m services.server")


if __name__ == "__main__":
    main()
