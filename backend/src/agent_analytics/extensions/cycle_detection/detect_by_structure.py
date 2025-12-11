from collections import Counter, defaultdict

from ibm_agent_analytics_common.interfaces.issues import IssueLevel

from agent_analytics.core.data_composite.issue import BaseIssue
from agent_analytics.core.data_composite.task import TaskComposite


class CycleDetector:
    def __init__(self, task_map: dict[str, TaskComposite]):
        """
        Initialize the cycle detector with a task map.

        Args:
            task_map: Dictionary mapping task IDs to TaskComposite objects
            cycle_thr: threshold for detecting cycles, default is 2, which means detect cycles with 2 or more repetitions of the same task name.
        """
        self.task_map = task_map

    def extract_task_name(self, full_name: str) -> str:
        """
        Extract the task name from the full name (part after ':').

        Args:
            full_name: The full task name (e.g., "0.2.0.3:validate")

        Returns:
            The extracted task name (e.g., "validate")
        """
        parts = full_name.split(':')
        return parts[1] if len(parts) > 1 else parts[0]

    def find_all_paths_dfs(self, start_id: str,
                           current_path: list[str], visited: set[str],
                           all_paths: list[list[str]], max_depth: int = 100):
        """
        Find all possible paths in the dependency graph using DFS.

        Args:
            start_id: Current task ID
            current_path: Current path being explored
            visited: Set of visited nodes in current path
            all_paths: List to store all found paths
            max_depth: Maximum depth to prevent infinite recursion
        """
        if len(current_path) > max_depth:
            return

        current_path.append(start_id)
        visited.add(start_id)

        # Get the current task and check its dependencies
        current_task = self.task_map[start_id]
        if current_task.dependent_ids:
            for dep_id in current_task.dependent_ids:
                if dep_id not in visited:
                    self.find_all_paths_dfs(dep_id, current_path.copy(),
                                            visited.copy(), all_paths, max_depth)
                else:
                    # Found a cycle - add the cyclic path
                    cycle_start_idx = current_path.index(dep_id)
                    cycle_path = current_path[cycle_start_idx:] + [dep_id]
                    all_paths.append(cycle_path)
        else:
            # End of path - add it to all_paths
            all_paths.append(current_path.copy())

        current_path.pop()
        visited.remove(start_id)

    def detect_cycles_with_repeated_names(self, min_occurrences: int = 2) -> tuple[list[list[TaskComposite]], list[list[str]], list[list[str]]]:
        """
        Detect cycles where task names (after ':') appear at least min_occurrences times.

        Args:
            min_occurrences: Minimum number of times a task name should appear in a cycle

        Returns:
            Tuple of (cycles_with_tasks, repeated_task_names, repeated_task_ids):
            - cycles_with_tasks: List of cycles, each containing TaskComposite objects
            - repeated_task_names: List of task names that appear >= min_occurrences times in each cycle
            - repeated_task_ids: List of task IDs that correspond to the repeated task names in each cycle
        """
        all_paths = []

        # Find all paths starting from each task
        for task_id in self.task_map.keys():
            self.find_all_paths_dfs(task_id, [], set(), all_paths)

        cycles_with_tasks = []
        repeated_task_names = []
        repeated_task_ids = []  # NEW: Added to track IDs of repeated tasks
        seen_cycles = set()  # To avoid duplicate cycles

        for path in all_paths:
            if len(path) < 2:
                continue

            # Extract task names for this path and find repeated task IDs
            task_names = []
            name_to_ids = defaultdict(list)  # Map task names to their IDs
            task_id_to_position = {}  # Map task IDs to their positions in the path

            for pos, task_id in enumerate(path):
                if task_id in self.task_map:
                    full_name = self.task_map[task_id].name
                    extracted_name = self.extract_task_name(full_name)
                    task_names.append(extracted_name)
                    name_to_ids[extracted_name].append(task_id)
                    task_id_to_position[task_id] = pos

            # Count occurrences of each task name
            name_counts = Counter(task_names)
            repeated_names = [name for name, count in name_counts.items() if count >= min_occurrences]

            if repeated_names:
                # Create a unique identifier for this cycle to avoid duplicates
                cycle_tasks = [self.task_map[task_id] for task_id in path if task_id in self.task_map]
                cycle_signature = tuple(sorted([task.id for task in cycle_tasks]))

                if cycle_signature not in seen_cycles:
                    seen_cycles.add(cycle_signature)
                    cycles_with_tasks.append(cycle_tasks)
                    repeated_task_names.append(repeated_names)

                    # NEW: Collect actual IDs of tasks that repeat (not grouped by name)
                    repeated_ids_for_cycle = []
                    for name in repeated_names:
                        # Get the actual task IDs that have this repeated name
                        ids_with_this_name = name_to_ids[name]
                        repeated_ids_for_cycle.append(ids_with_this_name)
                    repeated_task_ids.append(repeated_ids_for_cycle)

        return self.sort_tasks_by_name(cycles_with_tasks), repeated_task_names, repeated_task_ids

    @staticmethod
    def sort_tasks_by_name(tasks):
        """
        Sort a list of task objects by their name attribute (case-insensitive).

        Args:
            tasks: List of objects with a 'name' attribute

        Returns:
            List of tasks sorted alphabetically by name
        """
        for i in range(len(tasks)):
            tasks[i] = sorted(tasks[i], key=lambda task: task.name.lower())
        return tasks


    def is_subsequence_contained(self, cycle_a: list[TaskComposite], cycle_b: list[TaskComposite]) -> bool:
        """
        Check if cycle_a is contained as a subsequence in cycle_b.
        A is contained in B if all of A's tasks appear in B in the same order,
        while other tasks can be present in B between A's tasks.

        Args:
            cycle_a: Potentially contained cycle
            cycle_b: Potentially containing cycle

        Returns:
            True if cycle_a is a subsequence of cycle_b
        """
        if len(cycle_a) > len(cycle_b):
            return False

        a_ids = [task.id for task in cycle_a]
        b_ids = [task.id for task in cycle_b]

        # Check if a_ids is a subsequence of b_ids
        a_idx = 0
        for b_task_id in b_ids:
            if a_idx < len(a_ids) and b_task_id == a_ids[a_idx]:
                a_idx += 1
                if a_idx == len(a_ids):
                    return True

        return a_idx == len(a_ids)

    def filter_maximal_cycles(self, cycles_with_tasks: list[list[TaskComposite]],
                              repeated_task_names: list[list[str]],
                              repeated_task_ids: list[list[list[str]]]) -> tuple[list[list[TaskComposite]], list[list[str]], list[list[list[str]]]]:
        """
        Filter cycles to keep only maximal ones (cycles that are not contained as subsequences in any other cycle).

        Args:
            cycles_with_tasks: List of cycles with TaskComposite objects
            repeated_task_names: List of repeated task names for each cycle
            repeated_task_ids: List of task IDs corresponding to repeated task names

        Returns:
            Filtered lists containing only maximal cycles
        """
        if not cycles_with_tasks:
            return cycles_with_tasks, repeated_task_names, repeated_task_ids

        maximal_indices = []

        for i, cycle_i in enumerate(cycles_with_tasks):
            is_maximal = True

            for j, cycle_j in enumerate(cycles_with_tasks):
                if i == j:
                    continue

                # Check if cycle_i is properly contained as subsequence in cycle_j
                if (self.is_subsequence_contained(cycle_i, cycle_j) and
                        len(cycle_i) < len(cycle_j)):
                    is_maximal = False
                    break

            if is_maximal:
                maximal_indices.append(i)

        # Filter all lists based on maximal indices
        maximal_cycles = [cycles_with_tasks[i] for i in maximal_indices]
        maximal_names = [repeated_task_names[i] for i in maximal_indices]
        maximal_ids = [repeated_task_ids[i] for i in maximal_indices]

        return maximal_cycles, maximal_names, maximal_ids

    def detect_maximal_cycles_with_repeated_names(self, min_occurrences: int = 2) -> tuple[
        list[list[TaskComposite]], list[list[str]], list[list[list[str]]]]:
        """
        Detect maximal cycles where task names (after ':') appear at least min_occurrences times.

        Args:
            min_occurrences: Minimum number of times a task name should appear in a cycle

        Returns:
            Tuple of (cycles_with_tasks, repeated_task_names, repeated_task_ids):
            - cycles_with_tasks: List of maximal cycles, each containing TaskComposite objects
            - repeated_task_names: List of task names that appear >= min_occurrences times in each cycle
            - repeated_task_ids: List of task IDs that correspond to the repeated task names in each cycle
        """
        # First get all cycles
        all_cycles, all_names, all_ids = self.detect_cycles_with_repeated_names(min_occurrences)

        # Then filter to keep only maximal ones
        return self.filter_maximal_cycles(all_cycles, all_names, all_ids)

    def add_issue_per_cycle(self, cycles_with_tasks: list[list[TaskComposite]],
                     repeated_task_names: list[list[str]], trace_id:str = None, analytics_id:str = None):
        """
        add issue per cycle and attach all relevant tasks to it.
        Args:
            cycles_with_tasks: List of cycles with TaskComposite objects
            repeated_task_names: List of repeated task names for each cycle
            trace_id: trace id of all the created issues
            analytics_id: analytics id of cycle detection
        Returns:
        """
        new_issues = []
        for i, (cycle_tasks, repeated_names) in enumerate(zip(cycles_with_tasks, repeated_task_names, strict=False)):
            ts = min([task.start_time for task in cycle_tasks])
            issue = BaseIssue(
                root=trace_id,
                plugin_metadata_id=analytics_id,
                level=IssueLevel.WARNING,
                timestamp=str(ts),
                name=f'Cycle Detection Issue: cycle_no.{i+1}', # {span.element_id}
                description=self.get_cycle_description_message(cycle_tasks),
                related_to=[cycle_tasks[0]],
                effect=[task.name for task in cycle_tasks]
            )
            new_issues.append(issue)
        return new_issues

    def get_cycle_description_message(self, cycle_tasks):
        base_message ='There exists a cycle in system execution, starting from this task forward - some tasks may run more times than expected.\n'
        base_message += 'The cycle contains the following tasks:\n'
        for task in cycle_tasks:
            base_message += f'\t{task.name} (ID: {task.id})\n'
        return base_message

    def print_cycles(self, cycles_with_tasks: list[list[TaskComposite]],
                     repeated_task_names: list[list[str]],
                     repeated_task_ids: list[list[list[str]]] = None):
        """
        Print the detected cycles in a readable format.

        Args:
            cycles_with_tasks: List of cycles with TaskComposite objects
            repeated_task_names: List of repeated task names for each cycle
            repeated_task_ids: List of task IDs that correspond to repeated task names (optional)
        """
        if not cycles_with_tasks:
            print("No cycles detected with the specified criteria.")
            return

        print(f"Found {len(cycles_with_tasks)} cycle(s):")
        print("-" * 50)

        for i, (cycle_tasks, repeated_names) in enumerate(zip(cycles_with_tasks, repeated_task_names, strict=False)):
            print(f"\nCycle {i + 1}:")
            print(f"Repeated task names: {repeated_names}")
            if repeated_task_ids and i < len(repeated_task_ids):
                print(f"Repeated task IDs: {repeated_task_ids[i]}")
            print("Task sequence:")
            for j, task in enumerate(cycle_tasks):
                extracted_name = self.extract_task_name(task.name)
                print(f"  {j + 1}. {task.name} (ID: {task.id}) -> '{extracted_name}'")
