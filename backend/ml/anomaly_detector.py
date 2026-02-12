"""
Isolation Forest anomaly detector for procurement tenders.
Provides ML-based anomaly scoring that complements rule-based detection.

Design decisions:
- Sigmoid normalization anchored to training distribution so scores are
  stable across batches (adding/removing a tender doesn't shift others).
- SHAP TreeExplainer for exact per-sample feature attributions.
"""

import os
import pickle
import logging
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ml.features import FEATURE_COLUMNS

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "trained")


class AnomalyDetector:
    """
    Wraps Isolation Forest with feature scaling and SHAP explainability.
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
        # Sigmoid normalization anchors (set during fit)
        self.train_score_mean_: float = 0.0
        self.train_score_std_: float = 1.0
        # SHAP explainer (lazy-initialized after fit)
        self._explainer = None

    def fit(self, features_df: pd.DataFrame):
        """Train on a feature DataFrame (indexed by tender_id)."""
        X = features_df[self.feature_columns].fillna(0).values
        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)
        self.model.fit(X_scaled)

        # Anchor sigmoid normalization to training distribution
        train_scores = self.model.decision_function(X_scaled)
        self.train_score_mean_ = float(np.mean(train_scores))
        self.train_score_std_ = float(np.std(train_scores))
        if self.train_score_std_ < 1e-8:
            self.train_score_std_ = 1.0

        self.is_fitted = True
        self._init_explainer(X_scaled)

    def _init_explainer(self, X_background: np.ndarray | None = None):
        """Initialize SHAP TreeExplainer. Falls back gracefully."""
        try:
            import shap

            self._explainer = shap.TreeExplainer(self.model)
            logger.info("SHAP TreeExplainer initialized")
        except Exception as e:
            logger.warning("SHAP unavailable, falling back to deviation proxy: %s", e)
            self._explainer = None

    def _normalize_scores(self, raw_scores: np.ndarray) -> np.ndarray:
        """
        Sigmoid normalization anchored to training distribution.
        Stable regardless of batch composition.

        Mapping:
          training mean  -> ~50/100
          1 std below    -> ~73/100 (suspicious)
          2 std below    -> ~88/100 (very suspicious)
        """
        z = (raw_scores - self.train_score_mean_) / self.train_score_std_
        # Negative z = more anomalous, so invert
        normalized = 100.0 / (1.0 + np.exp(2.0 * z))
        return np.clip(normalized, 0, 100)

    def score(self, features_df: pd.DataFrame) -> pd.DataFrame:
        """
        Score tenders. Returns DataFrame with:
        - anomaly_score: 0-100 (higher = more anomalous)
        - is_anomaly: bool
        - feature_importance: dict of top contributing features (signed SHAP values)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X = features_df[self.feature_columns].fillna(0).values
        X_scaled = self.scaler.transform(X)

        # Raw scores: negative = more anomalous
        raw_scores = self.model.decision_function(X_scaled)
        predictions = self.model.predict(X_scaled)

        # Stable sigmoid normalization
        normalized = self._normalize_scores(raw_scores)

        # SHAP feature importance (exact per-sample attributions)
        importances = self._compute_feature_importance(X_scaled)

        results = []
        for i, tid in enumerate(features_df.index):
            results.append(
                {
                    "tender_id": tid,
                    "anomaly_score": float(normalized[i]),
                    "is_anomaly": bool(predictions[i] == -1),
                    "feature_importance": importances[i],
                }
            )

        return pd.DataFrame(results).set_index("tender_id")

    def _compute_feature_importance(self, X_scaled: np.ndarray) -> list[dict]:
        """
        Per-sample feature importance.
        Uses SHAP TreeExplainer when available, falls back to deviation proxy.
        Returns top 5 features with signed contribution values.
        """
        if self._explainer is not None:
            return self._shap_importance(X_scaled)
        return self._deviation_importance(X_scaled)

    def _shap_importance(self, X_scaled: np.ndarray) -> list[dict]:
        """Exact SHAP values from TreeExplainer."""
        shap_values = self._explainer.shap_values(X_scaled)
        importances = []
        for i in range(X_scaled.shape[0]):
            row = shap_values[i]
            # Pair feature names with SHAP values, sort by absolute magnitude
            pairs = sorted(
                zip(self.feature_columns, row),
                key=lambda x: abs(x[1]),
                reverse=True,
            )[:5]
            importances.append({name: round(float(val), 4) for name, val in pairs})
        return importances

    def _deviation_importance(self, X_scaled: np.ndarray) -> list[dict]:
        """Fallback: absolute deviation from scaled mean as proxy."""
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
            sorted_imp = dict(
                sorted(imp.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
            )
            importances.append(sorted_imp)
        return importances

    def save(self, name: str = "default"):
        """Persist model + normalization anchors to disk."""
        os.makedirs(MODEL_DIR, exist_ok=True)
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        with open(path, "wb") as f:
            pickle.dump(
                {
                    "scaler": self.scaler,
                    "model": self.model,
                    "feature_columns": self.feature_columns,
                    "train_score_mean": self.train_score_mean_,
                    "train_score_std": self.train_score_std_,
                },
                f,
            )

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
        self.train_score_mean_ = data.get("train_score_mean", 0.0)
        self.train_score_std_ = data.get("train_score_std", 1.0)
        self.is_fitted = True
        self._init_explainer()
        return True
