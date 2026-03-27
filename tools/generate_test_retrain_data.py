"""
tools/generate_test_retrain_data.py

Script para popular a base de dados com dados de teste para o novo
script de retreino (`train/ann/retrain_nn_from_feedback.py`).
"""
import sqlite3
import json
import uuid
from pathlib import Path
import sys

APP_ROOT = Path(__file__).resolve().parent.parent
if str(APP_ROOT) not in sys.path:
    sys.path.append(str(APP_ROOT))

from services.db_utils import get_db_connection
from slider_config import ALL_SLIDER_NAMES

DB_PATH = APP_ROOT / 'data' / 'nsp_plugin.db'

def generate_data():
    """Gera um registo em 'records' e feedback associado em 'granular_feedback'."""
    
    record_id_to_use = 99999  # Usar um ID alto para não colidir
    session_id = str(uuid.uuid4())
    
    # Valores de exemplo
    # Usar um caminho de imagem que existe para evitar FileNotFoundError
    # Vamos apontar para o próprio script como um placeholder de ficheiro
    image_path_placeholder = str(Path(__file__).resolve()) 
    
    exif_data = json.dumps({"iso": 400, "width": 6000, "height": 4000})
    original_develop_vector = json.dumps([0.0] * len(ALL_SLIDER_NAMES))
    
    try:
        with get_db_connection(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # 1. Inserir um registo falso na tabela 'records'
            # Usar INSERT OR IGNORE para não falhar se o registo já existir
            cursor.execute("""
                INSERT OR IGNORE INTO records (id, image_path, exif, develop_vector)
                VALUES (?, ?, ?, ?)
            """, (record_id_to_use, image_path_placeholder, exif_data, original_develop_vector))
            print(f"Registo de teste inserido/confirmado na tabela 'records' com ID: {record_id_to_use}")

            # 2. Inserir feedback granular associado
            # Simular que o utilizador aumentou a exposição e o contraste
            feedback_items = [
                {
                    "slider_name": "exposure",
                    "slider_index": ALL_SLIDER_NAMES.index("exposure"),
                    "predicted_value": 0.0,
                    "user_value": 0.5,
                    "delta": 0.5
                },
                {
                    "slider_name": "contrast",
                    "slider_index": ALL_SLIDER_NAMES.index("contrast"),
                    "predicted_value": 0.0,
                    "user_value": 10.0,
                    "delta": 10.0
                }
            ]
            
            for item in feedback_items:
                # Usar INSERT OR IGNORE para poder correr o script várias vezes sem duplicar
                cursor.execute("""
                    INSERT OR IGNORE INTO granular_feedback (
                        original_record_id, session_id, slider_name, slider_index,
                        predicted_value, user_value, delta_value, was_edited,
                        confidence_score, feedback_quality, is_outlier, validated, used_in_training
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record_id_to_use,
                    session_id,
                    item["slider_name"],
                    item["slider_index"],
                    item["predicted_value"],
                    item["user_value"],
                    item["delta"],
                    1, # was_edited
                    0.85, # confidence_score
                    0.8, # feedback_quality
                    0, # is_outlier
                    1, # validated
                    0  # used_in_training (IMPORTANTE: começar com 0)
                ))
            
            print(f"{len(feedback_items)} feedbacks de teste inseridos para o record ID {record_id_to_use}")

    except sqlite3.Error as e:
        print(f"Ocorreu um erro na base de dados: {e}")

if __name__ == '__main__':
    generate_data()
