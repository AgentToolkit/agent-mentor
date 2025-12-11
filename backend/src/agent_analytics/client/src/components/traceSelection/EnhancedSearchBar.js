import React, { useEffect, useRef } from 'react';
import { Search, Sliders } from 'lucide-react';
import { Input } from '../CarbonComponents';

const EnhancedSearchBar = ({
  searchQuery,
  setSearchQuery,
  serviceName,
  startDate,
  endDate,
  minSpans,
  onFilterChange,
  onSearch,
  handleAdvancedFilterClick,
  className = ""
}) => {
  const inputRef = useRef(null);
  const isUserEditingRef = useRef(false);

  // Parse a query string into structured filter data
  const parseQueryString = (queryStr) => {
    const result = {
      service: "",
      from: "",
      to: "",
      minSpans: "",
      text: ""
    };

    // Default to current values
    if (serviceName) result.service = serviceName;
    if (startDate) result.from = startDate;
    if (endDate) result.to = endDate;
    if (minSpans) result.minSpans = minSpans;

    // Extract filter keywords
    const serviceMatch = queryStr.match(/service:([^\s]+)/i);
    if (serviceMatch) {
      result.service = serviceMatch[1];
      queryStr = queryStr.replace(serviceMatch[0], "").trim();
    }

    const fromMatch = queryStr.match(/from:([^\s]+)/i);
    if (fromMatch) {
      result.from = fromMatch[1];
      queryStr = queryStr.replace(fromMatch[0], "").trim();
    }

    const toMatch = queryStr.match(/to:([^\s]+)/i);
    if (toMatch) {
      result.to = toMatch[1];
      queryStr = queryStr.replace(toMatch[0], "").trim();
    }

    const minSpansMatch = queryStr.match(/minspans:([^\s]+)/i);
    if (minSpansMatch) {
      result.minSpans = minSpansMatch[1];
      queryStr = queryStr.replace(minSpansMatch[0], "").trim();
    }

    // Remaining text is free search
    result.text = queryStr;

    return result;
  };

  // Handle search input changes
  const handleInputChange = (e) => {
    const newValue = e.target.value;
    isUserEditingRef.current = true;
    setSearchQuery(newValue);
  };

  // Handle search button click - using direct DOM access
  const handleSearchButtonClick = () => {
    // Get the input element directly
    const inputElement = document.getElementById('search-input');
    if (inputElement) {
      const newValue = inputElement.value;
      // Update the search query with the DOM value
      setSearchQuery(newValue);

      // Reset editing flag since user is committing the search
      isUserEditingRef.current = false;

      // Then trigger search with that value
      if (onSearch) {
        const parsedQuery = parseQueryString(newValue);
        onSearch(parsedQuery);
      }
    }
  };

  // Handle search submission
  const handleSubmit = (e) => {
    e.preventDefault();

    // Reset editing flag since user is committing the search
    isUserEditingRef.current = false;

    if (onSearch) {
      const parsedQuery = parseQueryString(searchQuery);
      onSearch(parsedQuery);
    }
  };

  // Focus the input and position cursor at the end
//   const focusInput = () => {
//     if (inputRef.current) {
//       inputRef.current.focus();
//       const length = inputRef.current.value.length;
//       inputRef.current.setSelectionRange(length, length);
//     }
//   };

  // Update the search query when any of serviceName, startDate, endDate, or minSpans changes
  // But only if the user is not actively editing the search bar
  useEffect(() => {
    // Don't overwrite user input while they're typing
    if (isUserEditingRef.current) {
      return;
    }

    let query = searchQuery;

    // Extract the free text part (without filter keywords)
    const parsed = parseQueryString(query);
    const freeText = parsed.text;

    // Build a new query with the current filter values
    query = "";

    if (serviceName) {
      query += `service:${serviceName} `;
    }

    if (startDate) {
      query += `from:${startDate} `;
    }

    if (endDate) {
      query += `to:${endDate} `;
    }

    if (minSpans) {
      query += `minspans:${minSpans} `;
    }

    // Add back the free text
    if (freeText) {
      query += freeText;
    }

    setSearchQuery(query.trim());
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serviceName, startDate, endDate, minSpans]);

  return (
    <form onSubmit={handleSubmit} className={`flex items-center w-full ${className}`}>
      <div className="relative flex-grow">
        <Input
          ref={inputRef}
          type="text"
          className="pl-10 pr-10 w-full"
          placeholder="Search by service:name from:YYYY-MM-DD or part of ID/name"
          value={searchQuery}
          onChange={handleInputChange}
          id="search-input"
        />
        <Search 
          size={20} 
          className="absolute left-3 top-1/2 transform -translate-y-1/2 text-[#525252]" 
        />
      </div>
      
      <button
        type="button"
        className="ml-2 p-2 text-[#525252] hover:text-[#161616]"
        onClick={handleSearchButtonClick}
        title="Search"
      >
        <Search size={20} />
      </button>
      <button
        type="button"
        className="ml-2 p-2 text-[#525252] hover:text-[#161616]"
        onClick={handleAdvancedFilterClick}
        title="Advanced Filters"
      >
        <Sliders size={20} />
      </button>
    </form>
  );
};

export default EnhancedSearchBar;