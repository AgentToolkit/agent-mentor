"""
Behavioral analyzer plugin — combines feature analysis with decision tree building.

For each node, discovers semantic features via LLM, extracts feature values,
encodes text features to boolean columns via embeddings + KMeans,
trains decision trees, evaluates with CV F1, and ranks all nodes.

Ported from:
- agentops/experiment_pipeline.py lines 438-581, 906-927
"""

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import polars as pl

from analytics.base_plugin import AnalyticsPlugin
from .prompt import (
    FEATURE_DISCOVERY_SYSTEM_PROMPT,
    FEATURE_DISCOVERY_USER_TEMPLATE,
    FEATURE_EXTRACTION_SYSTEM_PROMPT,
    FEATURE_EXTRACTION_USER_TEMPLATE,
    FEATURE_LIST_SCHEMA,
)


def _sanitize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", str(name).lower())


class BehavioralAnalyzerPlugin(AnalyticsPlugin):

    def __init__(self):
        self.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
        self.max_concurrent_extract = 10
        self.max_depth = 5
        self.importance_threshold = 0.015
        self.exclude_prefixes = [
            "result", "outcome", "exception", "error",
            "errorinfo", "useridentifier", "user_name", "username",
        ]

    @property
    def name(self) -> str:
        return "behavioral_analyzer"

    @property
    def description(self) -> str:
        return (
            "Discovers semantic features via LLM, extracts and encodes them, "
            "trains decision trees, and ranks agent nodes by behavioral separation quality"
        )

    def configure(self, config: Dict[str, Any]):
        self.embedding_model = config.get("embedding_model", self.embedding_model)
        self.max_concurrent_extract = config.get("max_concurrent_extract", self.max_concurrent_extract)
        self.max_depth = config.get("max_depth", self.max_depth)
        self.importance_threshold = config.get("importance_threshold", self.importance_threshold)
        self.exclude_prefixes = config.get("exclude_prefixes", self.exclude_prefixes)

    async def execute(self, state: "ApplicationState") -> Dict[str, Any]:
        # Register artifact kinds for experiment pipeline
        from analytics.plugins.trace_analyzer.models import ExperimentArtifact
        state._data_manager.register_artifact_kind("node_traces", ExperimentArtifact)
        state._data_manager.register_artifact_kind("feature_table", ExperimentArtifact)
        state._data_manager.register_artifact_kind("node_ranking", ExperimentArtifact)

        # Load node_traces artifacts from trace_analyzer
        result = await state.artifacts().kind("node_traces").get()
        node_traces_list = result.to_list() if result else []
        self._log(f"Found {len(node_traces_list)} node_traces artifacts")

        if not node_traces_list:
            return {
                "status": "skipped",
                "message": "No node_traces artifacts found",
                "artifacts_produced": 0,
            }

        from utils.llm_service import get_llm_service

        llm = get_llm_service()
        node_results = []
        artifacts_produced = 0

        # Process nodes in parallel — LLM calls across nodes overlap
        async def _process_one_node(node_traces_item):
            node_name = node_traces_item.get("node_name", "unknown")
            data = node_traces_item.get("data", {})
            aggregated = data.get("aggregated_traces", [])

            if not aggregated or len(aggregated) < 5:
                self._log(f"Insufficient traces for {node_name}, skipping.", level="warning")
                return None

            self._log(f"Analyzing node: {node_name} ({len(aggregated)} runs)")

            try:
                return await self._analyze_node(node_name, aggregated, llm)
            except Exception as e:
                self._log(f"Error analyzing {node_name}: {e}", level="error")
                return None

        parallel_results = await asyncio.gather(
            *[_process_one_node(nt) for nt in node_traces_list]
        )

        # Save artifacts sequentially after parallel analysis
        for result in parallel_results:
            if result is not None:
                await state.artifacts().from_plugin(self.name).kind("feature_table").save(
                    [result["feature_table_artifact"]]
                )
                node_results.append(result["ranking_entry"])
                artifacts_produced += 1

        if not node_results:
            return {
                "status": "skipped",
                "message": "No nodes could be analyzed successfully",
                "artifacts_produced": 0,
            }

        # Rank all nodes by cv_f1
        node_results.sort(key=lambda r: r["cv_f1"], reverse=True)
        ranking_artifact = {
            "name": "Node ranking by CV F1",
            "data": {"ranking": node_results},
        }
        await state.artifacts().from_plugin(self.name).kind("node_ranking").save(
            [ranking_artifact]
        )
        artifacts_produced += 1

        ranking_str = ", ".join(f"{r['node_name']}={r['cv_f1']:.3f}" for r in node_results)
        self._log(f"Node ranking: {ranking_str}")

        return {
            "status": "success",
            "artifacts_produced": artifacts_produced,
            "nodes_analyzed": len(node_results),
            "best_node": node_results[0]["node_name"] if node_results else None,
            "best_cv_f1": node_results[0]["cv_f1"] if node_results else 0,
        }

    # ── Per-Node Analysis ─────────────────────────────────────────

    async def _analyze_node(
        self, node_name: str, aggregated: List[Dict], llm
    ) -> Optional[Dict]:
        """Run full feature discovery → extraction → encoding → tree pipeline for one node."""

        # Build Polars DataFrame from aggregated traces
        df_agg = pl.DataFrame(aggregated)
        labels = df_agg["label"].to_list()

        # Step 1: Feature Discovery
        self._log(f"  [{node_name}] Step 1: Discovering features...")
        features = await self._discover_features(df_agg, llm)
        if not features:
            self._log(f"  [{node_name}] No features discovered, skipping.", level="warning")
            return None

        feature_descriptions = {_sanitize_name(f["name"]): f["description"] for f in features}
        self._log(f"  [{node_name}] Discovered {len(features)} features")

        # Step 2: Feature Extraction
        self._log(f"  [{node_name}] Step 2: Extracting feature values...")
        extracted_rows = await self._extract_features(
            df_agg["full_story"].to_list(), feature_descriptions, llm
        )

        if not extracted_rows or len(extracted_rows) < 5:
            self._log(
                f"  [{node_name}] Insufficient extracted data ({len(extracted_rows or [])} rows), skipping.",
                level="warning",
            )
            return None

        # Add labels back
        for i, row in enumerate(extracted_rows):
            if i < len(labels):
                row["cluster_label"] = int(labels[i])

        text_df = pl.DataFrame(extracted_rows)
        feature_cols = [c for c in text_df.columns if c != "cluster_label"]

        # Step 3: Boolean Encoding
        self._log(f"  [{node_name}] Step 3: Encoding to boolean features...")
        encoded_df, encoded_feature_cols = self._encode_to_booleans(text_df, feature_cols)

        if not encoded_feature_cols:
            self._log(f"  [{node_name}] No encoded features, skipping.", level="warning")
            return None

        # Step 4: Decision Tree
        self._log(f"  [{node_name}] Step 4: Building decision tree...")
        tree_result = self._build_decision_tree(
            encoded_df, encoded_feature_cols, labels, node_name
        )

        if not tree_result:
            self._log(f"  [{node_name}] Decision tree failed, skipping.", level="warning")
            return None

        self._log(
            f"  [{node_name}] Results: CV F1={tree_result['cv_f1']:.3f}, "
            f"accuracy={tree_result['accuracy']:.3f}, "
            f"depth={tree_result['tree_depth']}"
        )

        # Build artifacts
        feature_table_artifact = {
            "name": f"{node_name} feature table",
            "node_name": node_name,
            "data": {
                "feature_descriptions": feature_descriptions,
                "encoded_df": encoded_df.to_dicts(),
                "feature_columns": encoded_feature_cols,
                "labels": labels,
                "features_per_trace": text_df.to_dicts(),
                "tree_rules": tree_result["tree_rules"],
                "selected_features": tree_result["selected_features"],
                "feature_importance": tree_result["feature_importance"],
                "success_examples": [
                    r for r in text_df.to_dicts() if r.get("cluster_label") == 1
                ][:5],
                "failure_examples": [
                    r for r in text_df.to_dicts() if r.get("cluster_label") == 0
                ][:5],
            },
        }

        label_dist = df_agg.group_by("label").len().to_dicts()
        label_distribution = {str(r["label"]): r["len"] for r in label_dist}

        ranking_entry = {
            "node_name": node_name,
            "cv_f1": tree_result["cv_f1"],
            "accuracy": tree_result["accuracy"],
            "train_f1": tree_result["train_f1"],
            "tree_depth": tree_result["tree_depth"],
            "n_leaves": tree_result["n_leaves"],
            "n_features_selected": len(tree_result["selected_features"]),
            "selected_features": tree_result["selected_features"],
            "feature_importance": tree_result["feature_importance"][:15],
            "label_distribution": label_distribution,
            "n_traces": len(aggregated),
            "n_unique_runs": len(aggregated),
        }

        return {
            "feature_table_artifact": feature_table_artifact,
            "ranking_entry": ranking_entry,
        }

    # ── Feature Discovery ─────────────────────────────────────────

    async def _discover_features(self, df_agg: pl.DataFrame, llm) -> List[Dict]:
        """Use LLM to discover semantic features from success/failure examples."""
        examples_text = ""
        for label_id in sorted(df_agg["label"].unique().to_list()):
            subset = df_agg.filter(pl.col("label") == label_id)
            tag = "SUCCESS" if label_id == 1 else "FAILURE" if label_id == 0 else f"Label {label_id}"
            examples_text += f"\n--- {tag} ({len(subset)} traces) ---\n"
            for row in subset.head(20).iter_rows(named=True):
                examples_text += f"Trace:\n{row['full_story']}\n"

        prompt = FEATURE_DISCOVERY_USER_TEMPLATE.format(examples_text=examples_text)

        try:
            response = await llm.call_llm(
                user_prompt=prompt,
                system_prompt=FEATURE_DISCOVERY_SYSTEM_PROMPT,
                schema=FEATURE_LIST_SCHEMA,
                attributes={"temperature": 0, "max_tokens": 4096},
            )
            data = json.loads(response.content)
            features = self._parse_feature_list(data)
            return features if features else []
        except Exception as e:
            self._log(f"Feature discovery failed: {e}", level="error")
            return []

    @staticmethod
    def _parse_feature_list(data: Dict) -> List[Dict]:
        """Parse feature list from LLM response, handling various formats."""
        if isinstance(data, dict):
            if "features" in data:
                raw = data["features"]
            elif "feature_set" in data:
                raw = data["feature_set"]
            else:
                raw = [{"name": k, "description": str(v)} for k, v in data.items()]
        elif isinstance(data, list):
            raw = data
        else:
            return []

        features = []
        for item in raw:
            if isinstance(item, dict):
                name = item.get("name") or item.get("functional_name") or item.get("label", "")
                desc = item.get("description") or item.get("desc", "")
                if name:
                    features.append({"name": str(name), "description": str(desc)})

        return features

    # ── Feature Extraction ────────────────────────────────────────

    async def _extract_features(
        self, stories: List[str], feature_descriptions: Dict[str, str], llm
    ) -> List[Dict]:
        """Extract feature values for all traces using LLM with concurrency."""
        sem = asyncio.Semaphore(self.max_concurrent_extract)

        # Build dynamic JSON schema for extraction
        properties = {}
        for feat_name, feat_desc in feature_descriptions.items():
            properties[feat_name] = {"type": "string", "description": feat_desc}

        extraction_schema = {
            "type": "object",
            "properties": properties,
        }

        field_desc = "\n".join(
            f"- {name}: {desc}" for name, desc in feature_descriptions.items()
        )

        async def _extract_one(text: str) -> Optional[Dict]:
            async with sem:
                try:
                    safe_text = text[:12000]
                    prompt = FEATURE_EXTRACTION_USER_TEMPLATE.format(
                        field_desc=field_desc, trace_text=safe_text
                    )
                    response = await llm.call_llm(
                        user_prompt=prompt,
                        system_prompt=FEATURE_EXTRACTION_SYSTEM_PROMPT,
                        schema=extraction_schema,
                        attributes={"temperature": 0, "max_tokens": 2048},
                    )
                    data = json.loads(response.content)
                    # Force all values to lowercase strings
                    return {
                        k: str(v).lower().strip() if v else "none"
                        for k, v in data.items()
                        if k in feature_descriptions
                    }
                except Exception as e:
                    self._log(f"Extraction error: {e}", level="warning")
                    return None

        results = await asyncio.gather(*[_extract_one(s) for s in stories])
        return [r for r in results if r is not None]

    # ── Boolean Encoding ──────────────────────────────────────────

    def _encode_to_booleans(
        self, text_df: pl.DataFrame, feature_cols: List[str]
    ) -> tuple:
        """Encode text feature columns to boolean via embeddings + KMeans."""
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.cluster import KMeans
            from sklearn.metrics import silhouette_score, pairwise_distances_argmin_min
            import numpy as np
        except ImportError:
            self._log(
                "Missing deps. Install with: pip install agent-mentor[experiment]",
                level="error",
            )
            return pl.DataFrame(), []

        embedder = SentenceTransformer(self.embedding_model)
        all_bool_columns: Dict[str, List[int]] = {}
        n_rows = len(text_df)

        for col in feature_cols:
            raw_texts = text_df[col].fill_null("none").cast(pl.Utf8).to_list()
            if len(set(raw_texts)) < 2:
                continue

            embeddings = embedder.encode(raw_texts)
            optimal_k = self._find_optimal_k(embeddings, max_k=8)
            km = KMeans(n_clusters=optimal_k, random_state=42, n_init=10)
            cluster_labels = km.fit_predict(embeddings)

            # Name clusters based on closest sample to centroid
            closest, _ = pairwise_distances_argmin_min(km.cluster_centers_, embeddings)
            cluster_names = {}
            for c_id, idx in enumerate(closest):
                center_text = raw_texts[idx]
                clean = re.sub(r"[^a-zA-Z0-9\s]", "", center_text.lower())
                words = clean.split()
                safe_name = (
                    f"{words[0]}_..._{words[-1]}"
                    if len(words) > 5
                    else "_".join(words)
                )
                cluster_names[c_id] = safe_name[:40] or f"type{c_id}"

            for c_id in range(optimal_k):
                col_name = f"{col}_is_{cluster_names[c_id]}"
                all_bool_columns[col_name] = [
                    1 if cluster_labels[i] == c_id else 0 for i in range(n_rows)
                ]

        if not all_bool_columns:
            return pl.DataFrame(), []

        encoded_df = pl.DataFrame(all_bool_columns)
        return encoded_df, list(all_bool_columns.keys())

    @staticmethod
    def _find_optimal_k(embeddings, max_k: int = 8) -> int:
        """Find optimal number of clusters via silhouette score."""
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        n_samples = embeddings.shape[0]
        limit = min(max_k, n_samples - 1)
        if limit < 2:
            return 1

        best_k, best_score = 2, -1.0
        for k in range(2, limit + 1):
            try:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = km.fit_predict(embeddings)
                score = silhouette_score(embeddings, labels)
                if score > best_score:
                    best_k, best_score = k, score
            except Exception:
                continue
        return best_k

    # ── Decision Tree ─────────────────────────────────────────────

    def _build_decision_tree(
        self,
        encoded_df: pl.DataFrame,
        feature_cols: List[str],
        labels: List[int],
        node_name: str,
    ) -> Optional[Dict]:
        """Build and evaluate a decision tree classifier."""
        try:
            from sklearn.tree import DecisionTreeClassifier, export_text
            from sklearn.metrics import accuracy_score, f1_score
            from sklearn.model_selection import cross_val_score
            import numpy as np
        except ImportError:
            self._log(
                "Missing sklearn. Install with: pip install agent-mentor[experiment]",
                level="error",
            )
            return None

        # Filter out leaky prefixes
        process_cols = [
            c for c in feature_cols
            if not any(c.startswith(p) for p in self.exclude_prefixes)
        ]
        if not process_cols:
            return None

        X = encoded_df.select(process_cols).to_pandas().values
        y = np.array(labels[: X.shape[0]])
        col_names = process_cols

        # Feature selection pass
        selector = DecisionTreeClassifier(max_depth=self.max_depth, random_state=42)
        selector.fit(X, y)
        importances = selector.feature_importances_

        imp_data = sorted(
            zip(col_names, importances), key=lambda x: x[1], reverse=True
        )

        selected = [name for name, imp in imp_data if imp > self.importance_threshold]
        if not selected:
            selected = [name for name, _ in imp_data[:5]]

        selected_indices = [col_names.index(s) for s in selected]
        X_filtered = X[:, selected_indices]

        # Final tree
        clf = DecisionTreeClassifier(max_depth=self.max_depth, random_state=42)
        clf.fit(X_filtered, y)
        tree_rules = export_text(clf, feature_names=selected, max_depth=10)

        # Evaluate
        y_pred = clf.predict(X_filtered)
        accuracy = float(accuracy_score(y, y_pred))
        train_f1 = float(f1_score(y, y_pred, average="weighted"))

        label_counts = {}
        for lbl in y:
            label_counts[int(lbl)] = label_counts.get(int(lbl), 0) + 1

        n_cv = min(5, min(label_counts.values()))
        if n_cv >= 2:
            try:
                cv_scores = cross_val_score(
                    DecisionTreeClassifier(max_depth=self.max_depth, random_state=42),
                    X_filtered,
                    y,
                    cv=n_cv,
                    scoring="f1_weighted",
                )
                cv_f1 = float(cv_scores.mean())
            except Exception:
                cv_f1 = train_f1
        else:
            cv_f1 = train_f1

        # Save tree visualization
        self._save_tree_visualization(clf, selected, node_name)

        return {
            "cv_f1": cv_f1,
            "accuracy": accuracy,
            "train_f1": train_f1,
            "tree_depth": int(clf.get_depth()),
            "n_leaves": int(clf.get_n_leaves()),
            "tree_rules": tree_rules,
            "selected_features": selected,
            "feature_importance": [
                {"feature": name, "importance": round(float(imp), 6)}
                for name, imp in imp_data
            ],
        }

    def _save_tree_visualization(self, clf, feature_names: List[str], node_name: str):
        """Save decision tree as PNG visualization."""
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from sklearn.tree import plot_tree

            fig, ax = plt.subplots(figsize=(24, 12))
            plot_tree(
                clf,
                feature_names=feature_names,
                class_names=[str(c) for c in clf.classes_],
                filled=True,
                rounded=True,
                ax=ax,
                fontsize=10,
                proportion=True,
            )
            ax.set_title(
                f"Decision Tree \u2014 {node_name}", fontsize=16, fontweight="bold"
            )

            # Save to a temp location; the pipeline persistence handler will move it
            output_path = f"{node_name}_decision_tree.png"
            fig.savefig(output_path, dpi=150, bbox_inches="tight")
            plt.close(fig)
            self._log(f"  [{node_name}] Saved decision tree visualization: {output_path}")
        except Exception as e:
            self._log(f"  [{node_name}] Could not save tree visualization: {e}", level="warning")
