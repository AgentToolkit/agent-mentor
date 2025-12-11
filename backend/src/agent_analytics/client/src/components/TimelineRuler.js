import { useMemo } from "react";

const TimelineRuler = ({ startTime, endTime, width, zoom, baseWidth }) => {
  // Calculate the number of tick marks to show
  const getTicks = () => {
    // Dynamic tick spacing based on available width
    const totalDuration = endTime - startTime;
    let spacing;

    // Adjust tick spacing based on zoom level
    if (zoom <= 50) {
      spacing = totalDuration / 10; // 10 ticks
    } else if (zoom <= 100) {
      spacing = totalDuration / 20; // 20 ticks
    } else {
      spacing = totalDuration / 30; // 30 ticks for high zoom
    }

    // Ensure spacing is at least 1ms
    spacing = Math.max(spacing, 1);

    // Round to a nice value
    const magnitude = Math.pow(10, Math.floor(Math.log10(spacing)));
    const niceFactor = Math.ceil(spacing / magnitude);
    const niceSpacing = magnitude * (niceFactor === 1 ? 1 : niceFactor === 2 ? 2 : 5);

    // Generate tick positions
    const ticks = [];
    let current = 0;
    while (current <= totalDuration) {
      ticks.push({
        position: (current / totalDuration) * width,
        time: current,
      });
      current += niceSpacing;
    }

    return ticks;
  };

  // Generate ticks based on current width
  const ticks = useMemo(() => getTicks(), [startTime, endTime, width, zoom]);

  // Format time for display
  const formatTime = (ms) => {
    // Convert to seconds with one decimal place
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div style={{ position: "relative", width: `${width}px`, height: "30px" }}>
      {/* Ruler background */}
      <div
        style={{
          width: "100%",
          height: "30px",
          background: "white",
          borderBottom: "1px solid #e5e7eb",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Tick marks */}
        {ticks.map((tick, index) => (
          <div key={index} style={{ position: "absolute", left: `${tick.position}px` }}>
            {/* Tick mark line */}
            <div
              style={{
                height: "8px",
                width: "1px",
                background: "#9ca3af",
                marginLeft: "-0.5px",
              }}
            />

            {/* Time label */}
            <div
              style={{
                fontSize: "10px",
                color: "#4b5563",
                marginLeft: "-12px",
                marginTop: "2px",
                width: "24px",
                textAlign: "center",
              }}
            >
              {formatTime(tick.time)}
            </div>
          </div>
        ))}
      </div>

      {/* Grid lines extending down from each tick */}
      <div
        className="grid-lines"
        style={{ position: "absolute", top: "30px", left: 0, width: "100%", pointerEvents: "none" }}
      >
        {ticks.map((tick, index) => (
          <div
            key={`grid-${index}`}
            style={{
              position: "absolute",
              left: `${tick.position}px`,
              width: "1px",
              height: "5000px", // Very tall to extend through all content
              backgroundColor: "rgba(229, 231, 235)", // Light gray
              zIndex: 1,
            }}
          />
        ))}
      </div>
    </div>
  );
};

export default TimelineRuler;
