/**
 * Strips the task prefix (e.g., "0.0.1:") from a task name
 * @param {string} taskName - The original task name with prefix
 * @returns {string} - The task name without prefix
 */
export const stripTaskPrefix = (taskName) => {
  if (!taskName || typeof taskName !== 'string') {
    return taskName;
  }

  const colonIndex = taskName.indexOf(':');
  return colonIndex !== -1 ? taskName.substring(colonIndex + 1) : taskName;
};

/**
 * Conditionally strips task prefix based on user setting
 * @param {string} taskName - The original task name
 * @param {boolean} hidePrefixes - Whether to hide prefixes
 * @returns {string} - The processed task name
 */
export const formatTaskName = (taskName, hidePrefixes = false) => {
  if (!hidePrefixes) {
    return taskName;
  }
  return stripTaskPrefix(taskName);
};
