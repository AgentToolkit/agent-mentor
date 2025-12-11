import React from 'react';
import { formatDuration } from '../utils/traceUtils';

interface TimelineRulerProps {
  traceDuration: number; // in microseconds
  traceStartTime?: number;
}

const TimelineRuler: React.FC<TimelineRulerProps> = ({ traceDuration }) => {
  // Generate time markers (typically 10 markers across the timeline)
  const numMarkers = 10;
  const markers = Array.from({ length: numMarkers + 1 }, (_, i) => {
    const position = (i / numMarkers) * 100;
    const timeOffset = (i / numMarkers) * traceDuration;
    return { position, timeOffset };
  });

  return (
    <div className="h-full relative w-full">
      <div className="relative h-full">
        {markers.map((marker, index) => (
          <div
            key={index}
            className="absolute top-0 h-full -translate-x-1/2"
            style={{ left: `${marker.position}%` }}
          >
            <div className="w-px h-full bg-slate-300" />
            <div className="absolute top-1/2 left-1 -translate-y-1/2 text-[11px] text-slate-700 whitespace-nowrap font-medium">
              {formatDuration(marker.timeOffset)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default TimelineRuler;
