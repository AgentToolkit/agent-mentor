import { METRIC_ID } from './modalConstants';

// API functions for trace evaluation and fetching
export const fetchEvaluationStatus = async (authFetch, serverUrl, traceId) => {
  try {
    const response = await authFetch(`${serverUrl}/traces/${traceId}/analytics/${METRIC_ID}`);
    
    if (!response.ok) {
      console.error(`Failed to fetch evaluation status for trace ${traceId}`);
      return null;
    }
    
    const data = await response.json();
    return data.status;
  } catch (error) {
    console.error(`Error fetching evaluation status for trace ${traceId}:`, error);
    return null;
  }
};

export const launchEvaluation = async (authFetch, serverUrl, traceId) => {
  try {
    const response = await authFetch(`${serverUrl}/traces/${traceId}/analytics/${METRIC_ID}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        command: "launch"
      })
    });
    
    if (!response.ok) {
      console.error(`Failed to launch evaluation for trace ${traceId}`);
      return false;
    }
    
    return true;
  } catch (error) {
    console.error(`Error launching evaluation for trace ${traceId}:`, error);
    return false;
  }
};

export const fetchStorageTraces = async (authFetch, serverUrl, serviceName, startDate, endDate, minSpans) => {
  try {
    // Construct URL with query parameters for start and end dates if they exist
    let url = `${serverUrl}/storage/${serviceName}`;
    const params = new URLSearchParams();

    if (startDate) {
      params.append('startDate', startDate);
    }

    if (endDate) {
      params.append('endDate', endDate);
    }

    // Only add minSpans if it's set (non-empty string)
    if (minSpans) {
      params.append('minSpans', minSpans);
    }

    // Add query parameters to URL if any exist
    const queryString = params.toString();
    if (queryString) {
      url = `${url}?${queryString}`;
    }

    const response = await authFetch(url);
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    throw new Error('Error fetching from Storage: ' + error.message);
  }
};

export const createGroup = async (authFetch, serverUrl, serviceName, groupName, traceIds) => {
  try {
    const response = await authFetch(`${serverUrl}/storage/${serviceName}/groups`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: groupName,
        traceIds: traceIds
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(`Status: ${response.status} - ${errorData.detail || response.statusText}`);
    }

    const data = await response.json();
    if (data.error) {
      throw new Error(`${data.error}`);
    }
    
    return data;
  } catch (error) {
    throw new Error('Error creating group: ' + error.message);
  }
};

export const readFileAsJSON = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const jsonData = JSON.parse(e.target.result);
        resolve(jsonData);
      } catch (error) {
        reject(error);
      }
    };
    reader.onerror = (error) => reject(error);
    reader.readAsText(file);
  });
};