// Hierarchy building and data processing utilities

export const buildHierarchy = (data, setFilename, setTraceId) => {
  // Create a dictionary to store all items by their id
  const idMap = new Map(data.map((item) => [item.id, { ...item }]));

  // Create a dictionary to store children for each parent
  const childrenMap = new Map();

  // Identify root nodes and build children lists
  const rootNodes = [];
  setFilename('');
  data.forEach((item) => {
    const parentId = item.parent_id;
    if (parentId === undefined || parentId === null) {
      rootNodes.push(idMap.get(item.id));
      setFilename('Trace: ' + item.root_id);
      setTraceId(item.root_id);
    } else {
      if (!childrenMap.has(parentId)) {
        childrenMap.set(parentId, []);
      }
      childrenMap.get(parentId).push(idMap.get(item.id));
      setFilename('Trace: ' + item.log_reference.trace_id);
      setTraceId(item.log_reference.trace_id);
    }
  });

  const addChildren = (node) => {
    const nodeId = node.id;
    if (childrenMap.has(nodeId)) {
      node.children = childrenMap.get(nodeId);
      node.children.forEach((child) => addChildren(child));
    }
  };

  // Build the hierarchy starting from root nodes
  rootNodes.forEach((root) => addChildren(root));

  return rootNodes;
};

export const buildIssuesAndMetrics = (tasks, issues, analytics_metrics, trajectory) => {
  // Create a dictionary to store all items by their id
  const idMap = new Map(tasks.map((task) => [task.element_id, { ...task }]));

  // Store issues if they exist in the response
  if (issues && Array.isArray(issues)) {
    issues.forEach((issue) => {
      issue.related_elements = [];
      issue.related_to_ids.forEach((relatedId) => {
        const task = idMap.get(relatedId);
        issue.related_elements.push(task); // even if null
        if (task) {
          if (!task.issues) {
            task.issues = [];
          }
          task.issues.push(issue);
        }
      });
    });
  }

  let metrics = [];
  // Store metrics in tasks
  if (analytics_metrics && Array.isArray(analytics_metrics)) {
    analytics_metrics.forEach((metric) => {
      metric.related_to_types.forEach((relatedType, index) => {
        if (relatedType.includes('Task')) {
          const relatedId = metric.related_to_ids[index];
          const task = idMap.get(relatedId);
          if (task) {
            if (!task.metrics) {
              task.metrics = [];
            }
            metric.affected_task = task;
            task.metrics[metric.name] = metric.value;
          }
          if (metric.plugin_metadata_id === 'eval_metrics') {
            metrics.push(metric);
          }
        }
      });
    });
  }

  // prepare full task in steps
  if (trajectory && Array.isArray(trajectory)) {
    trajectory.forEach((step) => {
      step.task = idMap.get(step.task_id);
    });
  }

  return [issues, metrics];
};

// Function to find a task by ID in the hierarchy
export const findTaskById = (taskId, tasks) => {
  if (!tasks) return null;

  // Helper recursive function
  const findTask = (id, taskList) => {
    for (const task of taskList) {
      if (task.id === id) return task;

      if (task.children) {
        const found = findTask(id, task.children);
        if (found) return found;
      }
    }
    return null;
  };

  return findTask(taskId, tasks);
};
