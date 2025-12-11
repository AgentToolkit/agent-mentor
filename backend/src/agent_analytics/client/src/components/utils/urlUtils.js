// UrlUtils.js
/**
 * Updates URL parameters without page reload
 * @param {Object} params - Key-value pairs of parameters to set
 */
export const updateUrlParams = (params) => {
  // Get current URL parameters
  const url = new URL(window.location.href);
  const currentParams = {
    serviceName: url.searchParams.get('serviceName'),
    traceId: url.searchParams.get('traceId'),
    groupId: url.searchParams.get('groupId'),
    tabName: url.searchParams.get('tabName'),
  };

  // Update or add parameters
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === '') {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, value);
    }
  });

  // Create a full state object that merges current params with new ones
  const newState = { ...currentParams, ...params };

  // Update URL without reloading the page
  window.history.pushState(newState, '', url);

  // Log current URL state for debugging
  console.log('URL updated:', url.toString(), 'State:', newState);
};

/**
 * Gets all URL parameters relevant to the app
 * @returns {Object} Object containing URL parameters
 */
export const getUrlParams = () => {
  const url = new URL(window.location.href);
  return {
    serviceName: url.searchParams.get('serviceName'),
    traceId: url.searchParams.get('traceId'),
    groupId: url.searchParams.get('groupId'),
    tabName: url.searchParams.get('tabName'),
  };
};

/**
 * Registers a popstate event listener to handle browser back/forward navigation
 * @param {Function} callback - Function to call when navigation occurs
 */
export const setupHistoryListener = (callback) => {
  const popStateHandler = (event) => {
    // Log the event for debugging
    console.log('PopState event:', event.state);

    // Use event.state if it exists, otherwise get params from URL
    const params = event.state || getUrlParams();

    // Call the callback with the parameters
    callback(params);
  };

  window.addEventListener('popstate', popStateHandler);

  // Return cleanup function
  return () => {
    window.removeEventListener('popstate', popStateHandler);
  };
};
