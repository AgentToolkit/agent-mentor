import React from 'react';
import { ArrowLeft } from 'lucide-react';
import { Button, Input } from '../CarbonComponents';

const GroupCreation = ({
  serviceName,
  groupName,
  setGroupName,
  selectedTraces,
  tracesAndGroups,
  setModalState,
  handleSaveGroup,
  MODAL_STATES
}) => {
  // Get the traces that are selected
  const selectedTraceObjects = tracesAndGroups.filter(trace => selectedTraces.includes(trace.id));
  
  // Calculate earliest and latest timestamps for selected traces
  const timestamps = selectedTraceObjects.map(trace => new Date(trace.startTime || trace.timestamp || Date.now()));
  const earliestTimestamp = new Date(Math.min(...timestamps)).toLocaleDateString();
  const latestTimestamp = new Date(Math.max(...timestamps)).toLocaleDateString();
  
  return (
    <div className="p-6 h-full flex flex-col">
      <div className="mb-6">
        <button 
          className="flex items-center text-[#0f62fe] hover:text-[#0043ce]"
          onClick={() => setModalState(MODAL_STATES.TRACE_LIST)}
        >
          <ArrowLeft size={16} className="mr-1" />
          Back
        </button>
      </div>
      
      <h2 className="text-2xl font-normal text-[#161616] mb-8">New trace group</h2>
      
      <div className="grid grid-cols-1 gap-6 mb-8">
        <div>
          <h3 className="text-sm font-normal text-[#525252]">Service</h3>
          <p className="text-base text-[#161616]">{serviceName}</p>
        </div>
        
        <div>
          <h3 className="text-sm font-normal text-[#525252]">Traces</h3>
          <p className="text-base text-[#161616]">{selectedTraces.length}</p>
        </div>
        
        <div>
          <h3 className="text-sm font-normal text-[#525252]">Time range:</h3>
          <p className="text-base text-[#161616]">{earliestTimestamp} to {latestTimestamp}</p>
        </div>
        
        <div>
          <h3 className="text-sm font-normal text-[#525252] mb-2">Group name</h3>
          <Input
            type="text"
            placeholder="My new trace group"
            className="w-full"
            value={groupName}
            onChange={(e) => setGroupName(e.target.value)}
          />
        </div>
      </div>
      
      <div className="mt-auto flex items-center">
        <Button
          type="primary"
          onClick={handleSaveGroup} 
          disabled={groupName === ''}
        >
          Save
        </Button>
        <button
          className="ml-4 px-4 py-2 text-[#0f62fe] hover:text-[#0043ce]"
          onClick={() => setModalState(MODAL_STATES.TRACE_LIST)}
        >
          Cancel
        </button>
      </div>
    </div>
  );
};

export default GroupCreation;