import sqlite3
import json
import pandas as pd
from pathlib import Path
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class FeedbackCollector:
    def __init__(self, feedback_db_path='data/feedback.db'):
        """
        Sistema para coletar feedback e melhorar o modelo
        """
        self.feedback_db_path = Path(feedback_db_path)
        self.conn = None
        self._create_tables()
    
    def _connect(self):
        if not self.feedback_db_path.parent.exists():
            self.feedback_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.feedback_db_path)
        self.conn.row_factory = sqlite3.Row # Para aceder colunas por nome
    
    def _disconnect(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    def _create_tables(self):
        self._connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    image_path TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    predicted_preset INTEGER,
                    preset_confidence REAL,
                    predicted_params TEXT,
                    user_rating INTEGER,
                    user_edited BOOLEAN DEFAULT 0,
                    final_params TEXT,
                    notes TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feedback_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prediction_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    rating INTEGER,
                    tags TEXT,
                    issues TEXT,
                    notes TEXT,
                    delta_payload TEXT,
                    context TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(prediction_id) REFERENCES predictions(id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_events_prediction ON feedback_events(prediction_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_events_created ON feedback_events(created_at)")
            self.conn.commit()
            logger.info("Tabela 'predictions' verificada/criada com sucesso.")
        except Exception as e:
            logger.error(f"Erro ao criar tabela 'predictions': {e}")
        finally:
            self._disconnect()

    def log_prediction(self, image_path, prediction_result):
        """
        Regista uma predição
        """
        self._connect()
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO predictions 
                (image_path, predicted_preset, preset_confidence, predicted_params)
                VALUES (?, ?, ?, ?)
            """, (
                str(image_path),
                prediction_result['preset_id'],
                prediction_result['preset_confidence'],
                json.dumps(prediction_result['final_params'])
            ))
            self.conn.commit()
            logger.info(f"Predição registada para {image_path}. ID: {cursor.lastrowid}")
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"Erro ao registar predição para {image_path}: {e}")
            return None
        finally:
            self._disconnect()
    
    def add_feedback(
        self,
        prediction_id: int,
        rating: int,
        user_params: Optional[Dict[str, float]] = None,
        notes: str = '',
        feedback_type: str = "explicit",
        tags: Optional[List[str]] = None,
        issues: Optional[List[str]] = None,
        context: Optional[Dict[str, object]] = None
    ) -> Optional[int]:
        """
        Adiciona feedback do utilizador
        rating: 1-5 (1=péssimo, 5=perfeito)
        user_params: parâmetros finais se o utilizador editou
        """
        self._connect()
        try:
            cursor = self.conn.cursor()

            cursor.execute("SELECT predicted_params FROM predictions WHERE id = ?", (prediction_id,))
            row = cursor.fetchone()
            if row is None:
                logger.error(f"Predição ID {prediction_id} não encontrada para feedback.")
                return None

            predicted_params = json.loads(row["predicted_params"]) if row["predicted_params"] else {}

            user_edited = user_params is not None
            delta_payload = None
            if user_params:
                delta_payload = {}
                for slider, final_value in user_params.items():
                    delta_payload[slider] = final_value - predicted_params.get(slider, 0.0)
            
            cursor.execute("""
                UPDATE predictions
                SET user_rating = ?,
                    user_edited = ?,
                    final_params = ?,
                    notes = ?
                WHERE id = ?
            """, (
                rating,
                user_edited,
                json.dumps(user_params) if user_params else None,
                notes,
                prediction_id
            ))

            cursor.execute("""
                INSERT INTO feedback_events
                (prediction_id, event_type, rating, tags, issues, notes, delta_payload, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prediction_id,
                feedback_type,
                rating,
                json.dumps(tags or []),
                json.dumps(issues or []),
                notes,
                json.dumps(delta_payload) if delta_payload else None,
                json.dumps(context or {})
            ))
            event_id = cursor.lastrowid

            self.conn.commit()
            logger.info(f"Feedback adicionado para predição ID {prediction_id}. Rating: {rating} | event_id={event_id}")
            return event_id
        except Exception as e:
            logger.error(f"Erro ao adicionar feedback para predição ID {prediction_id}: {e}")
            return None
        finally:
            self._disconnect()
    
    def get_poor_predictions(self, rating_threshold=3):
        """
        Obtém predições com rating baixo para retreino
        """
        self._connect()
        try:
            query = """
                SELECT * FROM predictions
                WHERE user_rating <= ?
                AND user_edited = 1
                ORDER BY timestamp DESC
            """
            df = pd.read_sql_query(query, self.conn, params=(rating_threshold,))
            return df
        except Exception as e:
            logger.error(f"Erro ao obter poor predictions: {e}")
            return pd.DataFrame()
        finally:
            self._disconnect()
    
    def get_improvement_data(self):
        """
        Retorna dados para melhorar o modelo
        """
        improvements = []
        
        df = self.get_poor_predictions()
        
        for _, row in df.iterrows():
            predicted = json.loads(row['predicted_params'])
            final = json.loads(row['final_params']) if row['final_params'] else None
            
            if final:
                # Calcular diferenças
                diffs = {k: final.get(k, 0) - predicted.get(k, 0) 
                        for k in predicted.keys()}
                
                improvements.append({
                    'image_path': row['image_path'],
                    'predicted_preset': row['predicted_preset'],
                    'corrections': diffs,
                    'rating': row['user_rating']
                })
        
        return improvements

    def get_stats(self):
        """
        Obtém estatísticas agregadas do sistema de feedback.
        """
        self._connect()
        try:
            cursor = self.conn.cursor()
            
            # Total de predições
            cursor.execute("SELECT COUNT(*) FROM predictions")
            total_predictions = cursor.fetchone()[0]
            
            # Predições com feedback
            cursor.execute("SELECT COUNT(*) FROM predictions WHERE user_rating IS NOT NULL")
            with_feedback = cursor.fetchone()[0]
            
            # Rating médio
            cursor.execute("SELECT AVG(user_rating) FROM predictions WHERE user_rating IS NOT NULL")
            avg_rating = cursor.fetchone()[0] or 0.0
            
            # Distribuição de presets
            cursor.execute("""
                SELECT predicted_preset, COUNT(*) as count 
                FROM predictions 
                GROUP BY predicted_preset
                ORDER BY predicted_preset
            """)
            preset_distribution = {row[0]: row[1] for row in cursor.fetchall()}
            
            return {
                'total_predictions': total_predictions,
                'predictions_with_feedback': with_feedback,
                'average_rating': round(avg_rating, 2),
                'preset_distribution': preset_distribution,
                'feedback_rate': round(with_feedback / total_predictions * 100, 1) if total_predictions > 0 else 0.0
            }
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas do feedback: {e}")
            return {}
        finally:
            self._disconnect()
