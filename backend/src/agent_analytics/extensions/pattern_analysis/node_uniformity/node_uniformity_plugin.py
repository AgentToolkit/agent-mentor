from __future__ import annotations

import traceback
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple, Literal
from itertools import combinations
import hashlib
import json
import datetime
import re
import logging # MODIFIED: Replaced print with logging

import numpy as np
from pydantic import BaseModel, Field
# --- MODIFIED: Restored KMedoids / KMeans ---
# --- You might need: pip install scikit-learn-extra ---
try:
    from sklearn_extra.cluster import KMedoids
    HAS_KMEDOIDS = True
except ImportError:
    logging.warning("sklearn_extra.KMedoids not found. Falling back to basic KMeans (less ideal for cosine).")
    logging.warning("Consider installing it: pip install scikit-learn-extra")
    from sklearn.cluster import KMeans # Fallback
    HAS_KMEDOIDS = False

# --- MODIFIED: Restored pairwise_distances for KMedoids ---
from sklearn.metrics.pairwise import cosine_similarity, pairwise_distances
from sklearn.preprocessing import normalize
from sklearn.manifold import TSNE

from agent_analytics.core.data.base_data_manager import DataManager
from agent_analytics.core.data.trace_data import BaseTraceData
from agent_analytics.core.data.trace_group_data import TraceGroupData
from agent_analytics.core.data.trace_workflow_data import TraceWorkflowData
from agent_analytics.core.data.workflow_node_data import WorkflowNodeData
from agent_analytics.core.data.task_data import TaskData

from agent_analytics.core.data_composite.base_trace import BaseTraceComposite
from agent_analytics.core.data_composite.metric import BaseMetric, BaseNumericMetric
from agent_analytics.core.data_composite.task import TaskComposite
from agent_analytics.core.data_composite.trace_group import TraceGroupComposite

from agent_analytics.core.plugin.base_plugin import (
    BaseAnalyticsPlugin,
    ExecutionError,
    ExecutionResult,
    ExecutionStatus,
)

from agent_analytics.core.utilities.type_resolver import TypeResolutionUtils
from agent_analytics.extensions.pattern_analysis.task_embedding.sentence_trans_embedder import SentenceTransformerEmbedder

# ===========================
# Setup
# ===========================

logger = logging.getLogger(__name__)

# ===========================
# Constants
# ===========================

# --- Clustering & t-SNE ---
RANDOM_STATE = 42
DEFAULT_MAX_K_CLUSTERS = 5
TSNE_PERPLEXITY = 30
TSNE_MAX_ITER = 300

# --- Embeddings ---
DEFAULT_EMBEDDING_MODEL = "nli-distilroberta-base-v2"
DEFAULT_ATTRIBUTE_TO_EMBED = "output"

# --- Parsing ---
ROOT_NODE_NAME = "0:_ROOT"
TASK_FILE_SUFFIX = ".task"
CHAT_FILE_SUFFIX = ".chat"

# ===========================
# Helpers
# ===========================

def make_json_serializable(obj):
    if isinstance(obj, (str, int, float, bool, type(None))): return obj
    if isinstance(obj, (datetime.datetime, datetime.date)): return obj.isoformat()
    if isinstance(obj, np.ndarray): return obj.tolist()
    if isinstance(obj, (np.float32, np.float64)): return float(obj)
    if isinstance(obj, (np.int32, np.int64)): return int(obj)
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items() if k != '_data_manager'}
    if isinstance(obj, (list, tuple, set)):
        return [make_json_serializable(item) for item in obj]
    if hasattr(obj, '__dict__'):
        return make_json_serializable(vars(obj))
    return str(obj)

def extract_task_name_from_workflow(s: str) -> str:
    """Extracts the base task name from a workflow node string."""
    if s == ROOT_NODE_NAME: 
        return s
    if s.endswith(TASK_FILE_SUFFIX): 
        s = s[:-len(TASK_FILE_SUFFIX)]
    
    # Handle potential "1:MyAgent.chat" -> "1:MyAgent"
    if "." in s:
        s = s.rsplit(".", 1)[0]
    
    # Handle "1:MyAgent" -> "MyAgent"
    if ":" in s:
        s = s.rsplit(":", 1)[-1]
        
    return s

def extract_task_name_from_task(s: str) -> str:
    """Extracts the base task name from a task name string."""
    if s == ROOT_NODE_NAME: 
        return s
        
    # Handle "1:MyAgent" -> "MyAgent"
    if ":" in s:
        s = s.rsplit(":", 1)[-1]
        
    # Handle "MyAgent.chat" -> "MyAgent"
    if s.endswith(CHAT_FILE_SUFFIX): 
        s = s[:-len(CHAT_FILE_SUFFIX)]
        
    return s

# --- **** MODIFIED: Removed the complex `compute_uniformity_scores` function **** ---
# We will now use Average Pairwise Cosine Similarity as the "uniformity" metric.

def find_best_k_elbow_inertia(
    embeddings: np.ndarray, 
    max_k: int = DEFAULT_MAX_K_CLUSTERS
) -> Tuple[int, int, np.ndarray]:
    """
    Finds the optimal number of clusters (K) using the "Elbow Method"
    based on inertia.
    Tries KMedoids (sum of distances) if available, falls back to KMeans (WCSS).
    """
    total_samples = len(embeddings)
    if total_samples < 2:
        return 1, 0, np.array([0] * total_samples)
    
    # --- Precompute distance matrix for KMedoids (if available) ---
    distance_matrix = None
    if HAS_KMEDOIDS:
        # Note: pairwise_distances calculates 1 - cosine_similarity if metric='cosine'
        normalized_embeddings = normalize(embeddings, norm='l2', axis=1)
        distance_matrix = pairwise_distances(normalized_embeddings, metric='cosine')
        # Clamp tiny negative values potentially caused by floating point errors
        distance_matrix[distance_matrix < 0] = 0 
    
    inertias = []
    models = {} # Store fitted models to get labels later
    
    min_k = 1
    # We need at least K samples for K clusters
    effective_max_k = min(max_k, total_samples) 
    
    # We need at least two points (e.g., K=1 and K=2) to find an elbow
    if effective_max_k < 2:
        return 1, 0, np.zeros(total_samples, dtype=int)

    ks = range(min_k, effective_max_k + 1)
    valid_ks = [] # Keep track of Ks that succeeded

    for k in ks:
        try:
            clusterer = None
            if HAS_KMEDOIDS and distance_matrix is not None:
                # Using KMedoids with precomputed cosine distance
                # Its 'inertia_' is the sum of distances to medoids
                clusterer = KMedoids(n_clusters=k, metric='precomputed', init='k-medoids++', random_state=RANDOM_STATE)
                clusterer.fit(distance_matrix) # Fit on distances
            else: 
                # Fallback to KMeans (less ideal as it uses Euclidean)
                # Its 'inertia_' is the WCSS (sum of squared distances)
                clusterer = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
                clusterer.fit(embeddings) # Fit on raw embeddings

            inertias.append(clusterer.inertia_)
            models[k] = clusterer
            valid_ks.append(k)

        except ValueError as e:
            # This can happen if k > number of unique points, etc.
            logger.warning(f"Clustering failed for K={k}. Error: {e}. Stopping K search.")
            # We can't continue, so break the loop
            break # Stop at the K that failed

    # We need at least 2 valid points to find an elbow
    if len(valid_ks) < 2:
        best_k = 1
        best_labels = np.zeros(total_samples, dtype=int)
        return best_k, 0, best_labels

    # --- Find the elbow point using distance-from-line method ---
    
    # Create a 2D array of points: [ [k1, inertia1], [k2, inertia2], ... ]
    points = np.array([valid_ks, inertias]).T
    
    # Get the first and last points
    p1 = points[0]
    pN = points[-1]
    
    # Vector for the line from p1 to pN
    line_vec = pN - p1
    line_vec_norm = np.linalg.norm(line_vec)
    
    if line_vec_norm == 0:
        # All points are the same, just return K=1
        best_k = 1
        best_labels = models[best_k].labels_
        return best_k, 0, best_labels

    # Normalize the line vector
    line_vec_unit = line_vec / line_vec_norm
    
    # Get vectors from p1 to all intermediate points
    # We skip p1 and pN, as their distance is 0
    vecs_from_p1 = points[1:-1] - p1
    
    if vecs_from_p1.shape[0] == 0:
        # Only 2 points (e.g., K=1, K=2), no intermediate points. Default to K=1.
        best_k = 1
        best_labels = models[best_k].labels_
        return best_k, 0, best_labels
        
    # Project vecs_from_p1 onto line_vec_unit
    scalar_projections = np.dot(vecs_from_p1, line_vec_unit)
    projections = scalar_projections[:, np.newaxis] * line_vec_unit[np.newaxis, :]
    
    # Distances = norm of (vector - projection)
    dist_vectors = vecs_from_p1 - projections
    distances = np.linalg.norm(dist_vectors, axis=1)
    
    if not distances.any():
        best_k = 1 # Default to 1 if no clear elbow
    else:
        # The best K corresponds to the point with the max distance.
        best_k_index = np.argmax(distances) + 1
        best_k = valid_ks[best_k_index]
    
    best_labels = models[best_k].labels_

    # num_noise is 0 for these methods
    return best_k, 0, best_labels


def apply_manifold_learning(embeddings: np.ndarray, n_components: int = 2) -> np.ndarray:
    if len(embeddings) < 5:
        # Fallback for very small groups
        if n_components > embeddings.shape[1]:
            n_components = embeddings.shape[1]
        if len(embeddings) <= n_components: # Not enough samples
            if len(embeddings) == 1:
                return np.zeros((1, n_components)) # Single point
            # Pad with zeros if we must
            pad_width = ((0, 0), (0, n_components - embeddings.shape[1]))
            return np.pad(embeddings, pad_width, 'constant') if embeddings.shape[1] < n_components else embeddings[:, :n_components]

        # Simplified PCA-like fallback for small N
        try:
            if embeddings.shape[1] >= n_components:
                return embeddings[:, :n_components]
            else: # Pad if not enough features
                pad_width = ((0, 0), (0, n_components - embeddings.shape[1]))
                return np.pad(embeddings, pad_width, 'constant')
        except Exception:
            return np.zeros((len(embeddings), n_components)) # Final fallback
            
    perplexity = min(TSNE_PERPLEXITY, len(embeddings) - 1)
    # Ensure n_components is valid
    effective_n_components = n_components
    if len(embeddings) <= n_components:
        effective_n_components = max(1, len(embeddings) - 1)
    
    if effective_n_components < 2: # TSNE must have n_components >= 2
         if embeddings.shape[1] >= 2:
             return embeddings[:, :2] # Just return first 2 dims
         else:
             return np.zeros((len(embeddings), 2)) # Fallback

    tsne = TSNE(
        n_components=effective_n_components,
        perplexity=perplexity,
        metric='cosine',
        random_state=RANDOM_STATE,
        max_iter=TSNE_MAX_ITER,
        init='pca',
        learning_rate='auto'
    )
    return tsne.fit_transform(embeddings)

def _get_run_id(task) -> str:
    td = task.model_dump() if hasattr(task, "model_dump") else {}
    return str(td.get('log_reference', {}).get('trace_id') or td.get("trace_id") or td.get("root") or "RUN_UNKNOWN")

def _get_attribute_text(task, attribute: str) -> str:
    try:
        d = task._data_object
        txt = d.output.get("gen_ai.completion.0.content") if attribute == "output" else (d.input.get("gen_ai.prompt.1.content") or d.input.get("gen_ai.prompt.0.content"))
        if isinstance(txt, str): return re.sub(r"\s+", " ", txt).strip()
    except Exception as e:
        logger.warning(f"Could not extract attribute '{attribute}' from task {getattr(task, 'id', 'UNKNOWN')}. Error: {e}")
    return ""

def node_related_to_for_metrics(*, mode, root_id, key_workflow, key_node) -> Tuple[List[str], List[str]]:
    if key_workflow and key_node and key_workflow != "ALL":
        return [key_workflow, key_node], [TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceWorkflowData), TypeResolutionUtils.get_fully_qualified_type_name_for_type(WorkflowNodeData)]
    root_type = TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceGroupData if mode == "Group" else BaseTraceData)
    return [root_id], [root_type]

# ===========================
# Trajectory Similarity Helpers
# ===========================

def levenshtein_distance(seq1: List[str], seq2: List[str]) -> int:
    """Calculates the Levenshtein distance between two sequences of strings."""
    m, n = len(seq1), len(seq2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m + 1): dp[i][0] = i
    for j in range(n + 1): dp[0][j] = j
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if seq1[i - 1] == seq2[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return dp[m][n]

def sequence_similarity(seq1: List[str], seq2: List[str]) -> float:
    """Converts Levenshtein distance to a normalized similarity score (0-1)."""
    dist = levenshtein_distance(seq1, seq2)
    max_len = max(len(seq1), len(seq2))
    if max_len == 0: return 1.0
    return 1.0 - (dist / max_len)

def _get_action_from_task(task: TaskComposite) -> Optional[str]:
    """Extracts a simplified, representative action string from a task's output."""
    try:
        task_output_text = _get_attribute_text(task, "output")
        if not task_output_text: return None

        try: data = json.loads(task_output_text)
        except json.JSONDecodeError:
            return f"final_answer({hashlib.md5(task_output_text.encode()).hexdigest()[:6]})"

        if "instruction" in data: return str(data["instruction"]).strip()
        if "task_decomposition" in data and data["task_decomposition"]: return str(data["task_decomposition"][0].get("task")).strip()
        if "name" in data and "answer" in data: return f"qa: {data['name']}"
    except Exception: return None
    return None

# ===========================
# Data Loading / Grouping
# ===========================

async def _load_tasks_for_group(data_manager: DataManager, trace_ids: List[str]) -> Tuple[List[TaskComposite], Dict[str, List[TaskComposite]]]:
    """Helper to load all tasks for a group and organize them by trace."""
    tasks_by_trace: Dict[str, List[TaskComposite]] = {}
    all_tasks_in_group: List[TaskComposite] = []
    for trace_id in trace_ids:
        tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=trace_id)
        if tasks:
            tasks_by_trace[trace_id] = tasks
            all_tasks_in_group.extend(tasks)
    return all_tasks_in_group, tasks_by_trace

def parse_workflow_edges(trace_workflow_obj: Dict[str, Any]) -> Tuple[str, List[Tuple[str, str, str]]]:
    workflow_id = trace_workflow_obj["element_id"]
    edges: List[Tuple[str, str, str]] = []
    for item in trace_workflow_obj.get("workflow_nodes", []):
        if isinstance(item, str) and item.startswith("WorkflowNode"):
            a = item.find(":") + 1; b = item.find("#", a)
            parent = extract_task_name_from_workflow(item[a:b])
            a = b + 1; b = item.find("#", a)
            child = extract_task_name_from_workflow(item[a:b])
            edges.append((parent, child, item))
    return workflow_id, edges

def build_edge_catalogs(workflows) -> Tuple[Dict[str, Dict[Tuple[str, str], str]], set[Tuple[str, str]]]:
    edge_catalog_by_workflow: Dict[str, Dict[Tuple[str, str], str]] = {}
    edge_catalog_agg: set[Tuple[str, str]] = set()
    for wf in (workflows or []):
        wf_dict = wf.model_dump() if hasattr(wf, "model_dump") else wf
        workflow_id, edges = parse_workflow_edges(wf_dict)
        mapping = {(p, c): node_key for (p, c, node_key) in edges}
        edge_catalog_by_workflow[workflow_id] = mapping
        edge_catalog_agg.update(mapping.keys())
    return edge_catalog_by_workflow, edge_catalog_agg

def build_task_maps(tasks: List[TaskComposite]) -> Tuple[Dict[str, TaskComposite], Dict[str, str]]:
    task_by_id = {t.id: t for t in (tasks or [])}
    name_by_id: Dict[str, str] = {}
    for t in (tasks or []):
        td = t.model_dump()
        name_by_id[td["id"]] = extract_task_name_from_task(td["name"])
    return task_by_id, name_by_id

def group_tasks_by_edges(
    tasks: List[TaskComposite], name_by_id: Dict[str, str],
    edge_catalog_by_workflow: Dict[str, Dict[Tuple[str, str], str]],
    edge_catalog_agg: set[Tuple[str, str]], aggregate_across_workflows: bool,
) -> Dict[Tuple[str, str, str, str], List[TaskComposite]]:
    node_groups: Dict[Tuple[str, str, str, str], List[TaskComposite]] = defaultdict(list)
    for t in (tasks or []):
        td = t.model_dump()
        tid, parent_id = td["id"], td["parent_id"]
        if parent_id is None: continue
        child_name, parent_name = name_by_id.get(tid), name_by_id.get(parent_id)
        if not child_name or not parent_name: continue
        pair = (parent_name, child_name)
        if aggregate_across_workflows:
            if pair in edge_catalog_agg:
                key = ("ALL", parent_name, child_name, f"{parent_name}->{child_name}")
                node_groups[key].append(t)
        else:
            for wf_id, edge_map in edge_catalog_by_workflow.items():
                if pair in edge_map:
                    node_key = edge_map[pair]
                    key = (wf_id, parent_name, child_name, node_key)
                    node_groups[key].append(t)
    return node_groups

def preembed_by_task_id(
    vectorizer: SentenceTransformerEmbedder, tasks: List[TaskComposite], attribute: str
) -> Dict[str, np.ndarray]:
    if not tasks: return {}
    embs = vectorizer.embed_multiple(tasks, attributes=[attribute])
    return {t.id: embs[i] for i, t in enumerate(tasks)}

# ===========================
# Debug Saving
# ===========================

def save_debug_data_for_group(
    *, 
    key_workflow: str, 
    parent_name: str, 
    child_name: str, 
    group: List[TaskComposite],
    metrics: List[BaseNumericMetric],
    cluster_labels: np.ndarray,
    attribute_analyzed: str,
    max_examples_per_cluster: int = 3
):
    """Saves debug data, now including cluster examples with run_id and task_id."""
    source_data = [
        {
            "run_id": _get_run_id(task), 
            "task_id": task.id, 
            "text_analyzed": _get_attribute_text(task, attribute_analyzed),
            "cluster_label": int(label)
        }
        for task, label in zip(group, cluster_labels)
    ]
    
    cluster_examples: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    unique_labels = sorted(list(set(cluster_labels)))
    
    for label in unique_labels:
        cluster_name = f"Cluster {label}" if label != -1 else "Noise (Outliers)"
        tasks_in_cluster = [task for task, lbl in zip(group, cluster_labels) if lbl == label]
        
        example_count = 0
        for task in tasks_in_cluster:
            if example_count >= max_examples_per_cluster:
                break
            
            text = _get_attribute_text(task, attribute_analyzed)
            run_id = _get_run_id(task)
            
            if text:
                example_data = {
                    "run_id": run_id,
                    "task_id": task.id,
                    "text": text
                }
                cluster_examples[cluster_name].append(example_data)
                example_count += 1

    debug_package = {
        "group_info": {"workflow": key_workflow, "node": f"{parent_name}->{child_name}", "task_count": len(group)},
        "source_data": source_data,
        "calculated_metrics": [m.model_dump() for m in metrics],
        "cluster_examples": cluster_examples
    }
    
    safe_node_name = re.sub(r'[^\w\-_\.]', '_', f"{parent_name}-{child_name}")
    filename = f"debug_data_{key_workflow}_{safe_node_name}.json"
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(make_json_serializable(debug_package), f, indent=2)
        logger.info(f"Debug data saved to {filename}")
    except Exception as e:
        logger.error(f"Error saving debug file {filename}: {e}")


# ===========================
# Main Metric Calculation Functions
# ===========================

async def calculate_trajectory_similarity(
    *, tasks_by_trace: Dict[str, List[TaskComposite]], root_id: str, analytics_id: str,
) -> List[BaseNumericMetric]:
    """Calculates the average strategic similarity across all runs in a group."""
    trajectories: Dict[str, List[str]] = defaultdict(list)
    for trace_id, tasks in tasks_by_trace.items():
        sorted_tasks = sorted(tasks, key=lambda t: t.start_time)
        for task in sorted_tasks:
            action = _get_action_from_task(task)
            if action:
                trajectories[trace_id].append(action)

    run_ids = list(trajectories.keys())
    if len(run_ids) < 2: return []

    similarity_scores = [sequence_similarity(trajectories[r1], trajectories[r2]) for r1, r2 in combinations(run_ids, 2)]
    avg_similarity = np.mean(similarity_scores) if similarity_scores else 1.0

    return [BaseNumericMetric(
        element_id=f"Metric:TrajectoryUniformity:Group:{root_id}",
        plugin_metadata_id=analytics_id,
        root=root_id,
        name="Trajectory Uniformity", 
        description="Measures the strategic similarity of agent plans across different runs (1.0 is identical). Based on Levenshtein distance of action sequences.",
        related_to=([root_id], [TypeResolutionUtils.get_fully_qualified_type_name_for_type(TraceGroupData)]),
        value=float(avg_similarity),
        units="Similarity (0-1)"
    )]

# --- MODIFIED: Refactored to use Avg Cosine Sim as the Uniformity metric ---
def _calculate_metrics_for_single_group(
    *,
    X_high_dim: np.ndarray,
    root_id: str,
    mode: Literal["Group", "Trace"],
    analytics_id: str,
    key_workflow: str,
    parent_name: str,
    child_name: str,
    max_k_clusters: int
) -> Tuple[List[BaseNumericMetric], np.ndarray]:
    """Calculates all node-level metrics for a single group of embeddings."""
    
    metrics_for_this_group: List[BaseNumericMetric] = []

    kw = None if key_workflow == "ALL" else key_workflow
    rel_ids_node, rel_types_node = node_related_to_for_metrics(mode=mode, root_id=root_id, key_workflow=kw, key_node=None)
    el_id_base = f"Metric:NodeOutput:Group:{root_id}:{key_workflow or 'ALL'}:{parent_name}->{child_name}"

    # --- 1. Node Uniformity (Classic Metric) ---
    # We now use Average Pairwise Cosine Similarity as the primary uniformity metric.
    # We only need the upper triangle of the matrix, excluding the diagonal (k=1)
    sim_high_dim = cosine_similarity(X_high_dim)
    avg_cos_high_dim = float(np.mean(sim_high_dim[np.triu_indices_from(sim_high_dim, k=1)])) if len(X_high_dim) > 1 else 1.0
    
    metrics_for_this_group.append(BaseNumericMetric(
        element_id=f"{el_id_base}:Uniformity", # Renamed from :AvgCos
        plugin_metadata_id=analytics_id,
        root=root_id,
        name=f"Node Output Uniformity ({parent_name}→{child_name})", # Renamed
        description="Measures semantic consistency of outputs. Based on the Average Pairwise Cosine Similarity (1.0 is identical).", # Updated description
        related_to=(rel_ids_node, rel_types_node),
        value=avg_cos_high_dim,
        units='Avg. Cosine Similarity (-1 to 1)' # Updated units
    ))

    # --- 2. Clustering ---
    num_clusters, _, cluster_labels = find_best_k_elbow_inertia(
        X_high_dim,
        max_k=max_k_clusters
    )

    metrics_for_this_group.append(BaseNumericMetric(
        element_id=f"{el_id_base}:BehavioralClusters",
        plugin_metadata_id=analytics_id,
        root=root_id,
        name=f"Node Output Behavioral Clusters ({parent_name}→{child_name})",
        description=f"Optimal number of behavioral clusters (K=1-{max_k_clusters}) found using the Elbow Method on cluster inertia (K-Medoids/KMeans).",
        related_to=(rel_ids_node, rel_types_node),
        value=num_clusters,
        units="clusters"
    ))
    
    # --- MODIFIED: Removed the experimental t-SNE metric for simplicity ---
    
    return metrics_for_this_group, cluster_labels
# --- END REFACTORED FUNCTION ---

async def emit_metrics_for_groups(
    *,
    node_groups: Dict[Tuple[str, str, str, str], List["TaskComposite"]],
    root_id: str,
    mode: Literal["Group", "Trace"],
    analytics_id: str,
    vectorizer: "SentenceTransformerEmbedder",
    attribute: str,
    save_debug_files: bool,
    max_k_clusters: int
) -> List[BaseNumericMetric]:
    
    # --- Pre-embed all tasks at once ---
    all_tasks_dedup: Dict[str, "TaskComposite"] = {t.id: t for group_list in node_groups.values() for t in group_list}
    all_tasks = list(all_tasks_dedup.values())
    emb_by_task = preembed_by_task_id(vectorizer, all_tasks, attribute)

    out: List[BaseNumericMetric] = []
    
    # --- Iterate over each node group ---
    for (key_workflow, parent_name, child_name, _), group in node_groups.items():
        if len(group) < 2: 
            continue # Not enough data to compare

        # --- Filter embeddings for this specific group ---
        X_high_dim = np.stack([emb_by_task[t.id] for t in group if t.id in emb_by_task], axis=0)
        # Filter group to match embeddings actually found (handles potential preembed errors)
        valid_group = [t for t in group if t.id in emb_by_task]
        
        if len(X_high_dim) < 2: 
            continue # Need at least 2 points to cluster

        # --- MODIFIED: Call helper for metric calculation (k_value removed) ---
        metrics_for_this_group, cluster_labels = _calculate_metrics_for_single_group(
            X_high_dim=X_high_dim,
            root_id=root_id,
            mode=mode,
            analytics_id=analytics_id,
            key_workflow=key_workflow,
            parent_name=parent_name,
            child_name=child_name,
            max_k_clusters=max_k_clusters
        )
        
        # --- Save debug data if enabled ---
        if save_debug_files:
             if len(cluster_labels) == len(valid_group):
                 save_debug_data_for_group(
                     key_workflow=key_workflow, 
                     parent_name=parent_name, 
                     child_name=child_name,
                     group=valid_group, # Use the group corresponding to X_high_dim
                     metrics=metrics_for_this_group,
                     cluster_labels=cluster_labels,
                     attribute_analyzed=attribute
                 )
             else:
                  logger.warning(f"Mismatch between group size ({len(valid_group)}) and labels size ({len(cluster_labels)}). Skipping debug save for {parent_name}->{child_name}.")

        out.extend(metrics_for_this_group)
    
    return out

# ===========================
# I/O Models & Plugin
# ===========================

class NodeUniformityMetricInput(BaseModel):
    trace_id: Optional[str] = Field(default=None, description="Single trace ID to analyze")
    trace_group_id: Optional[str] = Field(default=None, description="Trace group ID to analyze across traces")

class NodeUniformityMetricOutput(BaseModel):
    trace_id: Optional[str] = Field(default=None, description="If single trace mode was used")
    trace_group_id: Optional[str] = Field(default=None, description="If group mode was used")
    metric_element_ids: List[str] = Field(description="Created uniformity metric IDs")

class NodeUniformityMetricPlugin(BaseAnalyticsPlugin):
    @classmethod
    def get_input_model(cls) -> type[NodeUniformityMetricInput]:
        return NodeUniformityMetricInput

    @classmethod
    def get_output_model(cls) -> type[NodeUniformityMetricOutput]:
        return NodeUniformityMetricOutput

    # --- MODIFIED: Refactored _execute to remove code duplication ---
    async def _execute(
        self,
        analytics_id: str,
        data_manager: DataManager,
        input_data: NodeUniformityMetricInput,
        config: Dict[str, Any]
    ) -> ExecutionResult:
        
        # --- 1. Validate Input & Load Config ---
        if not input_data.trace_id and not input_data.trace_group_id:
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="InputError",
                    message="Either trace_id or trace_group_id must be provided."
                )
            )

        try:
            # --- MODIFIED: Removed k_value ---
            attribute: str = str(config.get("attribute", DEFAULT_ATTRIBUTE_TO_EMBED))
            aggregate_across_workflows: bool = bool(config.get("aggregate_across_workflows", True))
            save_debug_files: bool = bool(config.get("save_debug_files", True))
            model_name: str = str(config.get("embedding_model_name", DEFAULT_EMBEDDING_MODEL))
            max_k_clusters: int = int(config.get("max_k_clusters", DEFAULT_MAX_K_CLUSTERS))
            
            logger.info(f"Using embedding model '{model_name}'")
            vectorizer = SentenceTransformerEmbedder(model_name)
            
            metrics_to_store = []
            
            # --- 2. Load Data (Consolidated Logic) ---
            all_tasks: List[TaskComposite] = []
            workflows = []
            root_id: str = ""
            mode: Literal["Group", "Trace"] = "Trace"

            if input_data.trace_group_id:
                root_id = input_data.trace_group_id
                mode = "Group"
                trace_group = await TraceGroupComposite.get_by_id(data_manager=data_manager, id=root_id)
                if not trace_group:
                    raise ValueError(f"No trace group found with id {root_id}")

                all_tasks, tasks_by_trace = await _load_tasks_for_group(data_manager, trace_group.traces_ids)
                
                # Add trajectory metrics ONLY in group mode
                trajectory_metrics = await calculate_trajectory_similarity(
                    tasks_by_trace=tasks_by_trace,
                    root_id=trace_group.element_id,
                    analytics_id=analytics_id
                )
                metrics_to_store.extend(trajectory_metrics)
                
                # Load workflows associated with the group
                workflows = await BaseTraceComposite.get_all_workflows_for_trace(data_manager=data_manager, trace_id=root_id)

            elif input_data.trace_id:
                root_id = input_data.trace_id
                mode = "Trace"
                tasks = await BaseTraceComposite.get_tasks_for_trace(data_manager=data_manager, trace_id=root_id)
                all_tasks = tasks or []
                workflows = await BaseTraceComposite.get_all_workflows_for_trace(data_manager=data_manager, trace_id=root_id)

            # --- 3. Handle Empty Data Case ---
            if not all_tasks:
                logger.info(f"No tasks found for {mode} {root_id}. Skipping metrics.")
                return ExecutionResult(
                    analytics_id=analytics_id,
                    status=ExecutionStatus.SUCCESS,
                    output=NodeUniformityMetricOutput(
                        trace_id=input_data.trace_id,
                        trace_group_id=input_data.trace_group_id,
                        metric_element_ids=[]
                    )
                )

            # --- 4. Process and Calculate Metrics (Common Logic) ---
            edge_by_wf, edge_agg = build_edge_catalogs(workflows)
            _, name_by_id = build_task_maps(all_tasks)
            node_groups = group_tasks_by_edges(
                tasks=all_tasks,
                name_by_id=name_by_id,
                edge_catalog_by_workflow=edge_by_wf,
                edge_catalog_agg=edge_agg,
                aggregate_across_workflows=aggregate_across_workflows
            )
            
            # --- MODIFIED: k_value parameter removed ---
            node_metrics = await emit_metrics_for_groups(
                node_groups=node_groups,
                root_id=root_id,
                mode=mode,
                analytics_id=analytics_id,
                vectorizer=vectorizer,
                attribute=attribute,
                save_debug_files=save_debug_files,
                max_k_clusters=max_k_clusters
            )
            metrics_to_store.extend(node_metrics)

            # --- 5. Store Results and Return ---
            if metrics_to_store:
                await BaseMetric.bulk_store(data_manager=data_manager, base_metrics=metrics_to_store)
            
            output = NodeUniformityMetricOutput(
                trace_id=input_data.trace_id,
                trace_group_id=input_data.trace_group_id,
                metric_element_ids=[m.element_id for m in metrics_to_store]
            )
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.SUCCESS,
                output=output
            )
            
        # --- 6. Error Handling ---
        except Exception as e:
            if "KMedoids" in str(e) and isinstance(e, NameError):
                 error_message = "KMedoids clustering failed. Ensure 'scikit-learn-extra' is installed (`pip install scikit-learn-extra`). Falling back to KMeans might yield suboptimal results for cosine distances."
                 logger.error(error_message)
                 return ExecutionResult(
                     analytics_id=analytics_id,
                     status=ExecutionStatus.FAILURE,
                     error=ExecutionError(
                         error_type="DependencyError",
                         message=error_message,
                         stacktrace=traceback.format_exc(),
                     )
                 )

            if "n_samples" in str(e) and "perplexity" in str(e):
                logger.warning(f"t-SNE failed, likely due to small sample size. {e}")
                # Return success with no metrics if this was the only error
                if not metrics_to_store:
                    return ExecutionResult(
                        analytics_id=analytics_id,
                        status=ExecutionStatus.SUCCESS,
                        output=NodeUniformityMetricOutput(
                            trace_id=input_data.trace_id,
                            trace_group_id=input_data.trace_group_id,
                            metric_element_ids=[]
                        )
                    )
            
            logger.error(f"Failed to process node uniformity metrics: {str(e)}", exc_info=True)
            return ExecutionResult(
                analytics_id=analytics_id,
                status=ExecutionStatus.FAILURE,
                error=ExecutionError(
                    error_type="ProcessingError",
                    message=f"Failed to process node uniformity metrics: {str(e)}",
                    stacktrace=traceback.format_exc(),
                )
            )