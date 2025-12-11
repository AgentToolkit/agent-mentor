import React, { useRef, useState, useEffect } from 'react';
import { X, Upload, ChevronDown, ChevronUp, History } from 'lucide-react';
import { Button, Input } from '../CarbonComponents';
import { storage } from '../AuthComponents';

const FilterPanel = ({
  serviceName,
  setServiceName,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  minSpans,
  setMinSpans,
  handleApplyFilters,
  handleCloseFilter,
  isFilterClosing,
  handleFileUpload,
  updateSearchQuery
}) => {
  const fileInputRef = useRef(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [serviceHistory, setServiceHistory] = useState([]);
  const [localName, setLocalName] = useState(serviceName);
  const [localMinSpans, setLocalMinSpans] = useState(minSpans);

  // Get service history on component mount
  useEffect(() => {
    const history = storage.getServiceHistory();
    setServiceHistory(history);
  }, []);

  // Function to handle selecting a service from history
  const handleSelectService = (name) => {
    setLocalName(name);
    setIsDropdownOpen(false);
  };

  // Function to handle service name change and update search query
  const handleServiceChange = (e) => {
    const newServiceName = e.target.value;
    setLocalName(newServiceName);
    // No need to update search query here as it will be handled in parent component's useEffect
  };

  // Function to handle date changes and update search query
  const handleDateChange = (type, value) => {
    if (type === 'start') {
      setStartDate(value);
    } else {
      setEndDate(value);
    }
    // No need to update search query here as it will be handled in parent component's useEffect
  };

  return (
    <div className={`w-80 bg-white border-r border-[#e0e0e0] h-full shadow-lg flex flex-col ${isFilterClosing ? 'filter-slide-out' : 'filter-slide-in'}`}>
      <div className="flex items-center justify-between p-4 border-b border-[#e0e0e0]">
        <h2 className="text-lg font-normal text-[#161616]">Advanced Filters</h2>
        <button onClick={handleCloseFilter} className="text-[#525252] hover:text-[#161616]">
          <X size={20} />
        </button>
      </div>
      
      <div className="p-4 space-y-6 flex-grow">
        <div>
          <label className="block text-sm font-normal text-[#525252] mb-2">
            Service name
          </label>
          <div className="relative">
            <Input
              type="text"
              value={localName}
              onChange={handleServiceChange}
              className="w-full pr-10"
              placeholder="Enter service name"
              onFocus={() => setIsDropdownOpen(true)}
            />
            <button
              className="absolute right-2 top-1/2 transform -translate-y-1/2 text-[#525252] hover:text-[#161616]"
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              aria-label={isDropdownOpen ? "Close service history" : "Open service history"}
            >
              {isDropdownOpen ? (
                <ChevronUp size={16} />
              ) : (
                <ChevronDown size={16} />
              )}
            </button>
            
            {/* Dropdown for service history */}
            {isDropdownOpen && serviceHistory.length > 0 && (
              <div className="absolute z-10 mt-1 w-full bg-white shadow-lg max-h-40 rounded-md py-1 text-base ring-1 ring-black ring-opacity-5 overflow-auto focus:outline-none sm:text-sm">
                <div className="flex items-center justify-between px-4 py-2 text-xs font-medium text-[#525252] bg-gray-50">
                  <span className="flex items-center">
                    <History size={14} className="mr-1" />
                    Recent Services
                  </span>
                  <span>{serviceHistory.length} items</span>
                </div>
                <ul>
                  {serviceHistory.map((name, index) => (
                    <li
                      key={index}
                      className="text-[#161616] hover:bg-[#e8f2ff] hover:text-[#0043ce] cursor-pointer px-4 py-2 text-sm"
                      onClick={() => handleSelectService(name)}
                    >
                      {name}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-1">Also available as "service:serviceName" in search bar</p>
        </div>
        
        <div>
          <label className={`block text-sm font-normal mb-2 ${startDate ? 'text-[#525252]' : 'text-[#8d8d8d]'}`}>Start date</label>
          <div className="relative">
            <input 
              type="date" 
              className={`w-full h-10 px-4 border-0 border-b-2 focus:outline-none focus:border-b-[#0f62fe] ${
                startDate 
                  ? 'bg-[#f4f4f4] border-b-[#8d8d8d]' 
                  : 'bg-[#f8f8f8] text-[#8d8d8d] border-b-[#c6c6c6]'
              }`}
              value={startDate}
              onChange={(e) => handleDateChange('start', e.target.value)}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">Also available as "from:YYYY-MM-DD" in search bar</p>
        </div>
        
        <div>
          <label className={`block text-sm font-normal mb-2 ${endDate ? 'text-[#525252]' : 'text-[#8d8d8d]'}`}>End date</label>
          <div className="relative">
            <input
              type="date"
              className={`w-full h-10 px-4 border-0 border-b-2 focus:outline-none focus:border-b-[#0f62fe] ${
                endDate
                  ? 'bg-[#f4f4f4] border-b-[#8d8d8d]'
                  : 'bg-[#f8f8f8] text-[#8d8d8d] border-b-[#c6c6c6]'
              }`}
              value={endDate}
              onChange={(e) => handleDateChange('end', e.target.value)}
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">Also available as "to:YYYY-MM-DD" in search bar</p>
        </div>

        <div>
          <label className={`block text-sm font-normal mb-2 ${localMinSpans ? 'text-[#525252]' : 'text-[#8d8d8d]'}`}>Minimum spans</label>
          <div className="relative">
            <input
              type="number"
              min="0"
              className={`w-full h-10 px-4 border-0 border-b-2 focus:outline-none focus:border-b-[#0f62fe] ${
                localMinSpans
                  ? 'bg-[#f4f4f4] border-b-[#8d8d8d]'
                  : 'bg-[#f8f8f8] text-[#8d8d8d] border-b-[#c6c6c6]'
              }`}
              value={localMinSpans}
              onChange={(e) => setLocalMinSpans(e.target.value)}
              placeholder="No minimum"
            />
          </div>
          <p className="text-xs text-gray-500 mt-1">Also available as "minspans:N" in search bar. Leave empty to disable filter.</p>
        </div>

        <Button
          type="primary"
          isFullWidth={true}
          onClick={(e) => {
              setServiceName(localName)
              setMinSpans(localMinSpans)
              handleApplyFilters(e, localName, localMinSpans)
            }
          }
          disabled={serviceName === ''}
        >
          Apply Filters
        </Button>
        
        <div className="flex items-center mt-2">
          <div className="w-full">
            <p className="text-xs text-gray-500">
              Apply these filters to search criteria. Once applied, you can edit them directly in the search bar.
            </p>
          </div>
        </div>
      </div>
      
      {/* Import section */}
      <div className="p-4 border-t border-[#e0e0e0]">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-normal text-[#161616]">Import</h2>
        </div>
        <Button
          type="primary"
          isFullWidth={true}
          onClick={() => fileInputRef.current?.click()}
          className="flex justify-between items-center"
        >
          <span>Upload Traces</span>
          <Upload className="w-4 h-4" />
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept=".log,.json"
          onChange={handleFileUpload}
          className="hidden"
          multiple
        />
      </div>
    </div>
  );
};

export default FilterPanel;