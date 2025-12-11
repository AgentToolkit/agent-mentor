// Format timestamp for display
export const formatTimestamp = (timestamp) => {
  if (!timestamp) return new Date().toLocaleDateString();

  const date = new Date(timestamp);
  const now = new Date();
  const diffInHours = (now - date) / (1000 * 60 * 60);

  // If within last 24 hours, show relative time + time
  if (diffInHours < 24) {
    const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diffInHours < 1) return `${Math.round(diffInHours * 60)}m ago`;
    return `${Math.round(diffInHours)}h ago, ${timeStr}`;
  }

  // If within last week, show day + time
  if (diffInHours < 168) {
    // 7 days
    const dayStr = date.toLocaleDateString([], { weekday: 'short' });
    const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    return `${dayStr}, ${timeStr}`;
  }

  // For older dates, show compact date + time
  const dateStr = date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return `${dateStr}, ${timeStr}`;
};
