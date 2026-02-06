"""
Isolation Forest anomaly detector for procurement tenders.
Provides ML-based anomaly scoring that complements rule-based detection.
"""

import os
import pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ml.features import FEATURE_COLUMNS

MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained")


class AnomalyDetector:
    """
    Wraps Isolation Forest with feature scaling and explainability.
    """

    def __init__(self, contamination: float = 0.15, n_estimators: int = 100):
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=n_estimators,
            random_state=42,
            n_jobs=-1,
        )
        self.is_fitted = False
        self.feature_columns = FEATURE_COLUMNS

    def fit(self, features_df: pd.DataFrame):
        """Train on a feature DataFrame (indexed by tender_id)."""
        X = features_df[self.feature_columns].fillna(0).values
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)
        self.model.fit(X_scaled)
        self.is_fitted = True

    def score(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Score tenders. Returns DataFrame with:
        - anomaly_score: 0-100 (higher = more anomalous)
        - is_anomaly: bool
        - feature_importance: dict of top contributing features
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X = features_df[self.feature_columns].fillna(0).values
        X_scaled = self.scaler.transform(X)

        # Raw scores: negative = more anomalous
        raw_scores = self.model.decision_function(X_scaled)
        predictions = self.model.predict(X_scaled)

        # Normalize to 0-100 scale (higher = more anomalous)
        min_s, max_s = raw_scores.min(), raw_scores.max()
        if max_s > min_s:
            normalized = 100 * (1 - (raw_scores - min_s) / (max_s - min_s))
        else:
            normalized = np.full_like(raw_scores, 50.0)

        # Feature importance via mean deviation from training mean
        importances = self._compute_feature_importance(X_scaled)

        results = []
        for i, tid in enumerate(features_df.index):
            results.append({
                "tender_id": tid,
                "anomaly_score": float(np.clip(normalized[i], 0, 100)),
                "is_anomaly": bool(predictions[i] == -1),
                "feature_importance": importances[i],
            })

        return pd.DataFrame(results).set_index("tender_id")

    def _compute_feature_importance(self, X_scaled: np.ndarray) -> list[dict]:
        """
        Approximate feature importance per sample.
        Uses absolute deviation from mean as a proxy for contribution.
        """
        # Mean of training data after scaling is ~0
        abs_deviation = np.abs(X_scaled)
        importances = []
        for i in range(X_scaled.shape[0]):
            row = abs_deviation[i]
            total = row.sum()
            if total == 0:
                imp = {col: 0.0 for col in self.feature_columns}
            else:
                imp = {
                    col: round(float(row[j] / total), 3)
                    for j, col in enumerate(self.feature_columns)
                }
            # Sort by importance descending, keep top 5
            sorted_imp = dict(sorted(imp.items(), key=lambda x: x[1], reverse=True)[:5])
            importances.append(sorted_imp)
        return importances

    def save(self, name: str = "default"):
        """Persist model to disk."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        with open(path, "wb") as f:
            pickle.dump({
                "scaler": self.scaler,
                "model": self.model,
                "feature_columns": self.feature_columns,
            }, f)

    def load(self, name: str = "default") -> bool:
        """Load model from disk. Returns True if successful."""
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        if not os.path.exists(path):
            return False
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.scaler = data["scaler"]
        self.model = data["model"]
        self.feature_columns = data["feature_columns"]
        self.is_fitted = True
        return True
