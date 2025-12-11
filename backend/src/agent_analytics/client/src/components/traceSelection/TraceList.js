import React, { useState, useEffect } from "react";
import {
  FolderKanban,
  FileText,
  CheckCircle,
  Clock,
  Activity,
  RefreshCw,
  CircleAlert,
  Loader,
  XCircle,
  Upload,
  ChevronUp,
  ChevronDown,
  Ban,
  AlertTriangle,
  AlertCircle,
  AlertOctagon,
} from "lucide-react";
import {
  Button,
  Checkbox,
  Tag,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeader,
} from "../CarbonComponents";
import { ANALYTICS_STATUS } from "./modalConstants";
import EnhancedSearchBar from "./EnhancedSearchBar";
import { formatTimestamp } from "../utils/timeUtils";

const TraceList = ({
  searchQuery,
  setSearchQuery,
  handleFilterButtonClick,
  handleCreateGroup,
  selectedTraces,
  serviceName,
  setServiceName,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  minSpans,
  setMinSpans,
  tracesAndGroups,
  handleSelectAllTraces,
  traces,
  handleSelectTrace,
  handleClick,
  handleRefreshStatus,
  handleLaunchEvaluation,
  onClose,
  handleUploadClick,
  handleApplyFilters,
  handleSearchExecute,
  extensionsEnabled,
}) => {
  // State for sorting
  const [sortField, setSortField] = useState("timestamp");
  const [sortDirection, setSortDirection] = useState("desc");
  const [refreshAnimationKeys, setRefreshAnimationKeys] = useState({});
  const [filteredItems, setFilteredItems] = useState([]);

  // Handle sorting when column header is clicked
  const handleSort = (field) => {
    if (sortField === field) {
      // Toggle direction if same field
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      // New field, set default to descending
      setSortField(field);
      setSortDirection("desc");
    }
  };

  // Update filtered items when search query or data changes
  useEffect(() => {
    // Extract free text search from the query string
    const parsedQuery = parseQueryString(searchQuery);
    const freeTextSearch = parsedQuery.text;

    // Filter items based on free text search
    const filtered = freeTextSearch
      ? tracesAndGroups.filter(
          (item) =>
            item.id.toLowerCase().includes(freeTextSearch.toLowerCase()) ||
            (item.name && item.name.toLowerCase().includes(freeTextSearch.toLowerCase()))
        )
      : tracesAndGroups;

    setFilteredItems(filtered);
  }, [searchQuery, tracesAndGroups]);

  // Parse a query string into structured filter data
  const parseQueryString = (queryStr) => {
    const result = {
      service: "",
      from: "",
      to: "",
      minSpans: "",
      text: "",
    };

    // Extract filter keywords - match even incomplete ones (with or without value)
    const serviceMatch = queryStr.match(/service:([^\s]*)/i);
    if (serviceMatch) {
      result.service = serviceMatch[1];
      queryStr = queryStr.replace(serviceMatch[0], "").trim();
    }

    const fromMatch = queryStr.match(/from:([^\s]*)/i);
    if (fromMatch) {
      result.from = fromMatch[1];
      queryStr = queryStr.replace(fromMatch[0], "").trim();
    }

    const toMatch = queryStr.match(/to:([^\s]*)/i);
    if (toMatch) {
      result.to = toMatch[1];
      queryStr = queryStr.replace(toMatch[0], "").trim();
    }

    const minSpansMatch = queryStr.match(/minspans:([^\s]*)/i);
    if (minSpansMatch) {
      result.minSpans = minSpansMatch[1];
      queryStr = queryStr.replace(minSpansMatch[0], "").trim();
    }

    // Remaining text is free search
    result.text = queryStr;

    return result;
  };

  // Handle search submission
  const handleSearch = (parsedQuery) => {
    // Update state if any of the filter values have changed
    if (parsedQuery.service !== serviceName) {
      setServiceName(parsedQuery.service);
    }

    if (parsedQuery.from !== startDate) {
      setStartDate(parsedQuery.from);
    }

    if (parsedQuery.to !== endDate) {
      setEndDate(parsedQuery.to);
    }

    if (parsedQuery.minSpans !== minSpans) {
      setMinSpans(parsedQuery.minSpans);
    }

    // Always trigger a search when user explicitly clicks search button
    // This fixes the bug where clicking magnifying glass doesn't re-fetch
    handleSearchExecute();
  };

  // Sort filtered items
  const getSortedItems = (items) => {
    return [...items].sort((a, b) => {
      // Handle group vs trace sorting differences
      let valueA, valueB;

      if (sortField === "type") {
        // Sort by type (group or trace)
        valueA = a.isGroup ? "Group" : "Trace";
        valueB = b.isGroup ? "Group" : "Trace";
      } else if (sortField === "timestamp") {
        // Sort by timestamp/startTime
        valueA = new Date(a.timestamp || a.startTime || Date.now());
        valueB = new Date(b.timestamp || b.startTime || Date.now());
      } else if (sortField === "name") {
        valueA = a.isGroup && a.name ? a.name.toLowerCase() : a.id.toLowerCase();
        valueB = b.isGroup && b.name ? b.name.toLowerCase() : b.id.toLowerCase();
      } else if (sortField === "contains") {
        valueA = a.isGroup ? a.traceCount || 0 : a.spansNum || 0;
        valueB = b.isGroup ? b.traceCount || 0 : b.spansNum || 0;
      } else if (sortField === "issues") {
        // Sort by issue severity (CRITICAL > ERROR > WARNING)
        const getIssuePriority = (item) => {
          if (!item.issue_dist) return 0;
          if (item.issue_dist.CRITICAL) return 3;
          if (item.issue_dist.ERROR) return 2;
          if (item.issue_dist.WARNING) return 1;
          return 0;
        };
        valueA = getIssuePriority(a);
        valueB = getIssuePriority(b);
      } else {
        // Default to sorting by id if field is not recognized
        valueA = a.id;
        valueB = b.id;
      }

      // Sorting logic
      if (sortDirection === "asc") {
        return valueA > valueB ? 1 : -1;
      } else {
        return valueA < valueB ? 1 : -1;
      }
    });
  };

  const sortedItems = getSortedItems(filteredItems);

  // Render issues information for a trace
  const renderIssues = (item) => {
    // Groups don't have individual issues
    if (item.isGroup) {
      return <span className="text-[#525252] text-xs">—</span>;
    }

    // No issues
    if (!item.issue_dist) {
      return <span className="text-[#525252] text-xs"></span>;
    }

    // Get issues in priority order
    const issueOrder = ["CRITICAL", "ERROR", "WARNING"];
    const issues = [];

    issueOrder.forEach((severity) => {
      if (item.issue_dist[severity]) {
        const count = Math.round(item.issue_dist[severity]);
        if (count > 0) {
          issues.push({ severity, count });
        }
      }
    });

    if (issues.length === 0) {
      return <span className="text-[#525252] text-xs">None</span>;
    }

    return (
      <div className="flex flex-wrap gap-1">
        {issues.slice(0, 3).map(({ severity, count }) => {
          let bgColor, textColor, icon;

          switch (severity) {
            case "CRITICAL":
              bgColor = "bg-purple-100";
              textColor = "text-purple-800";
              icon = <AlertOctagon size={10} className="mr-1" />;
              break;
            case "ERROR":
              bgColor = "bg-red-100";
              textColor = "text-red-800";
              icon = <AlertCircle size={10} className="mr-1" />;
              break;
            case "WARNING":
              bgColor = "bg-yellow-100";
              textColor = "text-yellow-800";
              icon = <AlertTriangle size={10} className="mr-1" />;
              break;
            default:
              bgColor = "bg-gray-100";
              textColor = "text-gray-800";
              icon = <AlertCircle size={10} className="mr-1" />;
          }

          return (
            <span
              key={severity}
              className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${bgColor} ${textColor}`}
            >
              {icon}
              {count}
            </span>
          );
        })}
      </div>
    );
  };

  // Render evaluation action button based on current status
  const renderEvaluationAction = (trace) => {
    const status = trace.analysisStatus?.advanced || ANALYTICS_STATUS.NOT_STARTED;

    if (status === ANALYTICS_STATUS.RUNNING) {
      const currentKey = refreshAnimationKeys[trace.id] || 0;

      return (
        <button
          className="text-blue-600 hover:text-blue-800 font-medium text-xs flex items-center"
          onClick={(e) => {
            e.stopPropagation();

            // Update the animation key for this specific trace
            setRefreshAnimationKeys((prev) => ({
              ...prev,
              [trace.id]: currentKey + 1,
            }));

            // Call the parent handler
            handleRefreshStatus(trace, e);
          }}
        >
          <RefreshCw
            key={currentKey} // This forces React to remount the icon
            size={12}
            className="mr-1 animate-spin-once"
          />
          Refresh
        </button>
      );
    } else if (status === ANALYTICS_STATUS.NOT_STARTED || status === ANALYTICS_STATUS.FAILED) {
      return (
        <button
          className="text-blue-600 hover:text-blue-800 font-medium text-xs flex items-center"
          onClick={(e) => handleLaunchEvaluation(trace, e)}
        >
          <Activity size={12} className="mr-1" />
          {status === "ERROR" ? "Retry" : "Launch!"}
        </button>
      );
    } else if (status === ANALYTICS_STATUS.COMPLETED) {
      return (
        <span className="text-green-600 font-medium text-xs flex items-center">
          <CheckCircle size={12} className="mr-1" />
          Completed
        </span>
      );
    } else if (status === ANALYTICS_STATUS.EMPTY) {
      return <span className="text-green-600 font-medium text-xs flex items-center"></span>;
    }

    return null;
  };

  // Render sort indicator for column headers
  const renderSortIcon = (field) => {
    if (sortField === field) {
      return sortDirection === "asc" ? <ChevronUp size={14} /> : <ChevronDown size={14} />;
    }
    return null;
  };

  return (
    <div className="flex flex-col h-full w-full">
      <div className="p-4 pl-8 flex items-center space-x-4 border-[#e0e0e0]">
        <div className="flex-grow">
          <EnhancedSearchBar
            searchQuery={searchQuery}
            setSearchQuery={setSearchQuery}
            serviceName={serviceName}
            startDate={startDate}
            endDate={endDate}
            minSpans={minSpans}
            onSearch={handleSearch}
            handleAdvancedFilterClick={handleFilterButtonClick}
          />
        </div>
        <button
          className="p-2 text-[#525252] hover:text-[#161616]"
          onClick={handleUploadClick}
          title="Upload"
          data-testid="upload-button"
        >
          <Upload size={20} />
        </button>
        <Button
          type={selectedTraces.length > 0 ? "primary" : "secondary"}
          disabled={selectedTraces.length === 0}
          onClick={handleCreateGroup}
        >
          Group
        </Button>
      </div>

      <div className="pl-8 pr-4 border-b border-[#d0e2ff] flex justify-between items-center py-2">
        <span className="text-[#0043ce]">
          {selectedTraces.length} trace{selectedTraces.length !== 1 ? "s" : ""} selected
        </span>
      </div>

      <div className="flex-1 overflow-auto border-l border-[#e0e0e0] ">
        <Table>
          <TableHead>
            <tr>
              <TableHeader className="w-12">
                <Checkbox
                  onChange={handleSelectAllTraces}
                  checked={selectedTraces.length === traces.length && traces.length > 0}
                />
              </TableHeader>
              <TableHeader className="cursor-pointer hover:bg-gray-50 w-48" onClick={() => handleSort("name")}>
                <div className="flex items-center">
                  Name/ID
                  {renderSortIcon("name")}
                </div>
              </TableHeader>
              <TableHeader className="cursor-pointer hover:bg-gray-50 w-32" onClick={() => handleSort("timestamp")}>
                <div className="flex items-center">
                  Timestamp
                  {renderSortIcon("timestamp")}
                </div>
              </TableHeader>
              <TableHeader className="w-28">Basic Analysis</TableHeader>
              {extensionsEnabled && (
                <TableHeader className="w-32">
                  Advanced Analysis <br></br>
                  <span className="lowercase">(Note: takes ~1min per span)</span>
                </TableHeader>
              )}
              <TableHeader className="cursor-pointer hover:bg-gray-50 w-20" onClick={() => handleSort("contains")}>
                <div className="flex items-center">
                  Contains
                  {renderSortIcon("contains")}
                </div>
              </TableHeader>
              <TableHeader className="cursor-pointer hover:bg-gray-50 w-24" onClick={() => handleSort("issues")}>
                <div className="flex items-center">
                  Issues
                  {renderSortIcon("issues")}
                </div>
              </TableHeader>
              <TableHeader className="cursor-pointer hover:bg-gray-50 w-20" onClick={() => handleSort("type")}>
                <div className="flex items-center">
                  Type
                  {renderSortIcon("type")}
                </div>
              </TableHeader>
            </tr>
          </TableHead>
          <TableBody>
            {sortedItems.map((item, index) => (
              <TableRow
                key={index}
                isSelected={!item.isGroup && selectedTraces.includes(item.id)}
                onClick={() => handleClick(item)}
                className={`cursor-pointer ${item.isGroup ? "bg-blue-50" : ""} hover:bg-gray-50`}
                data-testid="upload-success"
              >
                {item.isGroup || item.spansNum <= 2 ? (
                  <TableCell></TableCell>
                ) : (
                  <TableCell
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectTrace(item.id);
                    }}
                  >
                    <Checkbox checked={selectedTraces.includes(item.id)} onChange={() => {}} />
                  </TableCell>
                )}
                <TableCell>
                  <div className="flex items-center">
                    {item.isGroup ? (
                      <FolderKanban size={16} className="mr-2 text-blue-600" />
                    ) : (
                      <FileText size={16} className="mr-2 text-[#525252]" />
                    )}
                    <span className={`${item.isGroup ? "text-blue-700 font-medium" : "text-[#161616]"} truncate`}>
                      {item.isGroup && item.name ? item.name : item.id}
                    </span>
                  </div>
                </TableCell>
                <TableCell className="text-xs">
                  <div className="whitespace-nowrap overflow-hidden">
                    {formatTimestamp(item.timestamp || item.startTime)}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex space-x-2 items-center">
                    {!item.isGroup && item.spansNum > 2 && (
                      <Tag
                        type={
                          item.analysisStatus?.basic === ANALYTICS_STATUS.COMPLETED
                            ? "green"
                            : item.analysisStatus?.basic === ANALYTICS_STATUS.FAILED
                              ? "red"
                              : item.analysisStatus?.basic === ANALYTICS_STATUS.EMPTY
                                ? "black"
                                : "default"
                        }
                      >
                        {item.analysisStatus?.basic === ANALYTICS_STATUS.COMPLETED ? (
                          <>
                            <CheckCircle size={12} className="mr-1" />
                            Complete
                          </>
                        ) : item.analysisStatus?.basic === ANALYTICS_STATUS.FAILED ? (
                          <>
                            <CircleAlert size={12} className="mr-1" />
                            Failed
                          </>
                        ) : item.analysisStatus?.basic === ANALYTICS_STATUS.EMPTY ? (
                          <>
                            <Ban size={12} className="mr-1" />
                            Empty
                          </>
                        ) : (
                          <>
                            <Clock size={12} className="mr-1" />
                            Not Started
                            <button
                              className="text-blue-600 hover:text-blue-800 font-medium text-xs flex items-center"
                              onClick={(e) => handleClick(item)}
                            ></button>
                          </>
                        )}
                      </Tag>
                    )}
                    {item.analysisStatus.basic &&
                    ![ANALYTICS_STATUS.COMPLETED, ANALYTICS_STATUS.FAILED, ANALYTICS_STATUS.EMPTY].includes(
                      item.analysisStatus.basic
                    ) ? (
                      <span className="text-blue-600 hover:text-blue-800 font-medium text-xs flex items-center">
                        <Activity size={12} className="mr-1" />
                        Launch!
                      </span>
                    ) : (
                      <></>
                    )}
                  </div>
                </TableCell>
                {extensionsEnabled && (
                  <TableCell>
                    <div>
                      {!item.isGroup && item.spansNum > 2 && (
                        <div className="flex items-center space-x-2">
                          {(() => {
                            // Determine the status using a single mechanism
                            const status = item.analysisStatus?.advanced || ANALYTICS_STATUS.NOT_STARTED;

                            // Set the tag properties based on status
                            let tagType, icon, text;

                            switch (status) {
                              case ANALYTICS_STATUS.COMPLETED:
                                tagType = "green";
                                icon = <CheckCircle size={12} className="mr-1" />;
                                text = "Completed";
                                break;
                              case ANALYTICS_STATUS.RUNNING:
                                tagType = "blue";
                                icon = <Loader size={12} className="mr-1 animate-spin" />;
                                text = "Running";
                                break;
                              case ANALYTICS_STATUS.FAILED:
                                tagType = "red";
                                icon = <XCircle size={12} className="mr-1" />;
                                text = "Failed";
                                break;
                              case ANALYTICS_STATUS.EMPTY:
                                tagType = "black";
                                icon = <Ban size={12} className="mr-1" />;
                                text = "Empty";
                                break;
                              default:
                                tagType = "default";
                                icon = <Clock size={12} className="mr-1" />;
                                text = "Not Started";
                            }

                            return (
                              <Tag type={tagType}>
                                {icon}
                                {text}
                              </Tag>
                            );
                          })()}

                          {!item.isGroup && item.spansNum > 2 && (
                            <div className="flex flex-col">{renderEvaluationAction(item)}</div>
                          )}
                        </div>
                      )}
                    </div>
                  </TableCell>
                )}
                <TableCell>
                  {item.isGroup
                    ? item.traceCount
                      ? `${item.traceCount} Trace${item.traceCount > 1 ? "s" : ""}`
                      : "—"
                    : item.spansNum
                      ? `${item.spansNum} Span${item.spansNum > 1 ? "s" : ""}`
                      : "—"}
                </TableCell>
                <TableCell>{renderIssues(item)}</TableCell>
                <TableCell>
                  <Tag type={item.isGroup ? "blue" : "gray"}>{item.isGroup ? "Group" : "Trace"}</Tag>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="border-t border-[#e0e0e0] p-4 flex justify-end">
        <Button type="secondary" onClick={onClose}>
          Cancel
        </Button>
      </div>
    </div>
  );
};

export default TraceList;
