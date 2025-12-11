import { useState, useEffect, useRef } from "react";
import {
  ChevronDown,
  Code,
  ToggleLeft,
  ToggleRight,
  ChevronLeft,
  ChevronRight,
  Search,
  PanelLeftClose,
  Lightbulb,
  Eye,
  Play,
  FileText,
  LetterText,
  Images,
  Terminal,
  Database,
} from "lucide-react";
import { Button, Tag, InlineNotification } from "./CarbonComponents";
import ReactMarkdown from "react-markdown";
import TreeNode from "./TreeNode";
import Base64ImageViewer from "./trajectory/ImageViewer";
import { formatTaskName } from "./utils/taskNameUtils";

const StepNavigation = ({ currentStep, totalSteps, onPrev, onNext }) => {
  return (
    <div className="flex items-center space-x-2 mb-2">
      <div className="flex items-center bg-gray-100 rounded-lg p-1">
        <Button
          type="ghost"
          size="small"
          onClick={onPrev}
          disabled={currentStep === 0}
          className="flex items-center h-8 px-3"
        >
          <ChevronLeft className="w-4 h-4 mr-1" />
          Prev
        </Button>

        <div className="px-3 font-medium">
          Step {currentStep + 1} of {totalSteps}
        </div>

        <Button
          type="ghost"
          size="small"
          onClick={onNext}
          disabled={currentStep === totalSteps - 1}
          className="flex items-center h-8 px-3"
        >
          Next
          <ChevronRight className="w-4 h-4 ml-1" />
        </Button>
      </div>
    </div>
  );
};

const SearchBar = ({ onSearch }) => {
  const [searchTerm, setSearchTerm] = useState("");

  const handleSearch = (e) => {
    e.preventDefault();
    onSearch(searchTerm);
  };

  const handleInputChange = (e) => {
    const newTerm = e.target.value;
    setSearchTerm(newTerm);

    // Auto-search after a short delay
    if (newTerm === "") {
      onSearch("");
    }
  };

  return (
    <div className="flex items-center mb-2">
      <form onSubmit={handleSearch} className="flex w-full max-w-md">
        <div className="relative flex-grow">
          <input
            type="text"
            placeholder="Search trajectory steps..."
            value={searchTerm}
            onChange={handleInputChange}
            className="w-full h-10 px-4 py-2 pr-10 border border-gray-300 rounded bg-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
          />
          <button
            type="submit"
            className="absolute right-0 top-0 bottom-0 px-4 flex items-center justify-center bg-transparent"
          >
            <Search className="w-4 h-4 text-gray-500" />
          </button>
        </div>
      </form>
      {searchTerm && (
        <Button
          type="ghost"
          size="small"
          className="ml-2"
          onClick={() => {
            setSearchTerm("");
            onSearch("");
          }}
        >
          Clear
        </Button>
      )}
    </div>
  );
};

const JsonTreeNode = ({ name, value, level = 0, isOpen = true }) => {
  const [isExpanded, setIsExpanded] = useState(isOpen);

  const renderValue = (val) => {
    if (val === null) return <span className="text-gray-500">null</span>;
    if (typeof val === "boolean") return <span className="text-blue-600">{val.toString()}</span>;
    if (typeof val === "number") return <span className="text-green-600">{val}</span>;
    if (typeof val === "string") return <span className="text-red-600">"{val}"</span>;
    if (Array.isArray(val)) return `Array(${val.length})`;
    if (typeof val === "object") return `Object(${Object.keys(val).length})`;
    return val.toString();
  };

  const isExpandable = (val) => {
    return val && (typeof val === "object" || Array.isArray(val));
  };

  const hasExpandableContent = isExpandable(value);

  return (
    <div className={`${level > 0 ? "ml-4" : ""}`}>
      <div className="flex items-center">
        {hasExpandableContent && (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="mr-1 p-0.5 hover:bg-gray-200 rounded"
          >
            {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          </button>
        )}

        {name && <span className="text-purple-600 font-medium mr-2">"{name}":</span>}

        <span>{renderValue(value)}</span>
      </div>

      {hasExpandableContent && isExpanded && (
        <div className="ml-2">
          {Array.isArray(value)
            ? value.map((item, index) => (
                <JsonTreeNode key={index} name={index.toString()} value={item} level={level + 1} isOpen={level < 3} />
              ))
            : Object.entries(value).map(([key, val]) => (
                <JsonTreeNode key={key} name={key} value={val} level={level + 1} isOpen={level < 3} />
              ))}
        </div>
      )}
    </div>
  );
};

// Code block component with language-specific formatting
const CodeBlock = ({ language, code, searchTerm, blockId = Math.random().toString(36) }) => {
  const [jsonView, setJsonView] = useState("tree"); // 'tree' or 'json'

  const highlightText = (text, term) => {
    if (!term || !text) return text;
    const parts = text.split(new RegExp(`(${term})`, "gi"));
    return parts.map((part, index) =>
      part.toLowerCase() === term.toLowerCase() ? (
        <span key={index} className="bg-yellow-200">
          {part}
        </span>
      ) : (
        part
      )
    );
  };

  const getLanguageColor = (lang) => {
    const colors = {
      python: "bg-blue-100 text-blue-800",
      javascript: "bg-yellow-100 text-yellow-800",
      json: "bg-green-100 text-green-800",
      sql: "bg-purple-100 text-purple-800",
      bash: "bg-gray-100 text-gray-800",
      shell: "bg-gray-100 text-gray-800",
    };
    return colors[lang.toLowerCase()] || "bg-gray-100 text-gray-800";
  };

  const renderJsonContent = () => {
    if (language.toLowerCase() !== "json") return null;

    // Helper function to convert Python-style dictionaries to JSON
    const convertToValidJson = (code) => {
      try {
        // First try direct parsing (handles proper JSON)
        JSON.parse(code);
        return code; // Already valid JSON
      } catch (e) {
        try {
          // Try converting Python-style single quotes to double quotes and escape newlines
          let converted = code
            .replace(/'/g, '"') // Convert single quotes to double quotes
            .replace(/True/g, "true") // Convert Python booleans
            .replace(/False/g, "false")
            .replace(/None/g, "null")
            .replace(/\n/g, "\\n") // Escape actual newlines
            .replace(/\r/g, "\\r") // Escape carriage returns
            .replace(/\t/g, "\\t"); // Escape tabs

          // Test if conversion worked
          JSON.parse(converted);
          return converted;
        } catch (e2) {
          return null; // Conversion failed
        }
      }
    };

    const validJsonCode = convertToValidJson(code);

    try {
      const parsedJson = validJsonCode ? JSON.parse(validJsonCode) : null;

      return (
        <div className="mt-2">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <span className="text-base text-gray-600 pl-3">View:</span>
              <button
                type="button"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setJsonView(jsonView === "tree" ? "json" : "tree");
                }}
                className="flex items-center space-x-1 px-2 py-1 rounded text-sm hover:bg-gray-200"
              >
                {jsonView === "tree" ? (
                  <ToggleRight className="w-5 h-5 text-green-600" />
                ) : (
                  <ToggleLeft className="w-5 h-5 text-gray-500" />
                )}
                <span>{jsonView === "tree" ? "Tree" : parsedJson ? "JSON" : "Raw"}</span>
              </button>
            </div>
          </div>

          {jsonView === "tree" && parsedJson ? (
            <div className="bg-gray-50 border rounded p-3 max-h-96 overflow-auto">
              <JsonTreeNode name="" value={parsedJson} />
            </div>
          ) : (
            <div className="bg-gray-900 text-gray-100 rounded p-3 max-h-96 overflow-auto">
              <pre className="text-sm font-mono whitespace-pre">
                {highlightText(validJsonCode || code, searchTerm)}
              </pre>
            </div>
          )}
        </div>
      );
    } catch (e) {
      // Fallback - show raw data with toggle
      return (
        <div className="mt-2">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <span className="text-base text-gray-600 pl-3">Raw Data</span>
            </div>
          </div>
          <div className="bg-gray-900 text-gray-100 rounded p-3 max-h-96 overflow-auto">
            <pre className="text-sm font-mono whitespace-pre">{highlightText(code, searchTerm)}</pre>
          </div>
        </div>
      );
    }
  };

  const renderRegularCode = () => {
    const bgColor = language.toLowerCase() === "python" ? "bg-gray-900 text-gray-100" : "bg-gray-900 text-gray-100";

    return (
      <div className={`${bgColor} rounded p-3 max-h-96 overflow-auto`}>
        <pre className="text-sm font-mono whitespace-pre">{highlightText(code, searchTerm)}</pre>
      </div>
    );
  };

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden my-4">
      <div className={`px-3 py-2 border-b border-gray-200 flex items-center space-x-2 ${getLanguageColor(language)}`}>
        <Code className="w-4 h-4" />
        <span className="text-sm font-medium capitalize">{language}</span>
      </div>

      {language.toLowerCase() === "json" ? renderJsonContent() : renderRegularCode()}
    </div>
  );
};

// Enhanced message viewer component that preserves all original functionality
const EnhancedMessageViewer = ({ element, searchTerm, Base64ImageViewer, TreeNode }) => {
  const highlightText = (text, term) => {
    if (!term || !text) return text;
    const parts = text.split(new RegExp(`(${term})`, "gi"));
    return parts.map((part, index) =>
      part.toLowerCase() === term.toLowerCase() ? (
        <span key={index} className="bg-yellow-200">
          {part}
        </span>
      ) : (
        part
      )
    );
  };

  // Helper function to extract data blocks from text
  const extractDataBlocksFromText = (text) => {
    const dataBlockRegex = /^(\s*)data:\s*(\[[\s\S]*?\]|\{[\s\S]*?\})$/gm;
    const parts = [];
    let lastIndex = 0;
    let match;

    while ((match = dataBlockRegex.exec(text)) !== null) {
      // Add text before the data block
      if (match.index > lastIndex) {
        const beforeText = text.slice(lastIndex, match.index);
        if (beforeText.trim()) {
          parts.push({
            type: "text",
            content: beforeText,
          });
        }
      }

      // Add the data block as JSON
      const jsonData = match[2].trim();
      parts.push({
        type: "code",
        language: "json",
        content: jsonData,
      });

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      const remainingText = text.slice(lastIndex);
      if (remainingText.trim()) {
        parts.push({
          type: "text",
          content: remainingText,
        });
      }
    }

    // If no data blocks found, return the original text
    return parts.length > 0 ? parts : [{ type: "text", content: text }];
  };

  const parseCodeBlocks = (message) => {
    // Regex to match code blocks with language specifiers
    const codeBlockRegex = /```(\w+)?\n?([\s\S]*?)```/g;
    // Regex to match JSON-like data blocks that aren't in proper code fences
    const dataBlockRegex = /^(\s*)data:\s*(\[[\s\S]*?\]|\{[\s\S]*?\})$/gm;

    const parts = [];
    let processedMessage = message;
    let lastIndex = 0;
    let match;

    // First, find and mark data blocks that look like JSON
    const dataMatches = [];
    let dataMatch;
    while ((dataMatch = dataBlockRegex.exec(message)) !== null) {
      dataMatches.push({
        start: dataMatch.index,
        end: dataMatch.index + dataMatch[0].length,
        content: dataMatch[2].trim(),
        fullMatch: dataMatch[0],
      });
    }

    // Process regular code blocks
    while ((match = codeBlockRegex.exec(processedMessage)) !== null) {
      // Check if this code block overlaps with any data blocks
      const isOverlapping = dataMatches.some(
        (dataMatch) => match.index < dataMatch.end && match.index + match[0].length > dataMatch.start
      );

      if (isOverlapping) continue; // Skip overlapping matches

      // Add text before the code block
      if (match.index > lastIndex) {
        const beforeText = processedMessage.slice(lastIndex, match.index);
        if (beforeText.trim()) {
          // Check if this text contains any data blocks we should extract
          const textWithDataBlocks = extractDataBlocksFromText(beforeText);
          parts.push(...textWithDataBlocks);
        }
      }

      // Add the code block
      const language = match[1] || "text";
      const code = match[2].trim();
      parts.push({
        type: "code",
        language: language,
        content: code,
      });

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text after the last code block
    if (lastIndex < processedMessage.length) {
      const remainingText = processedMessage.slice(lastIndex);
      if (remainingText.trim()) {
        const textWithDataBlocks = extractDataBlocksFromText(remainingText);
        parts.push(...textWithDataBlocks);
      }
    }

    return parts.length > 0 ? parts : [{ type: "text", content: message }];
  };

  const renderContent = () => {
    const { message, title } = element;

    // Handle image data - preserve original Base64ImageViewer
    if (typeof message === "string" && message.startsWith("data:image")) {
      return (
        <div>
          <div className="text-base font-bold">{title}</div>
          {Base64ImageViewer ? (
            <Base64ImageViewer imageData={message} />
          ) : (
            <div className="bg-gray-100 p-4 rounded text-center">
              <FileText className="w-8 h-8 mx-auto text-gray-500 mb-2" />
              <span className="text-gray-600">Image content</span>
            </div>
          )}
        </div>
      );
    }

    // Try to parse as JSON first
    let parsedJson = null;
    try {
      parsedJson = JSON.parse(message);
    } catch (e) {
      // Not JSON, continue with regular processing
    }

    // If it's valid JSON and doesn't contain code blocks, handle JSON display
    if (parsedJson && !message.includes("```")) {
      return (
        <div>
          <div className="text-base font-bold">{title}</div>
          <div className="mt-2">
            {/* Use enhanced JSON viewer for better experience */}
            <CodeBlock language="json" code={message} searchTerm={searchTerm} blockId={`${title}-main-json`} />
          </div>
        </div>
      );
    }

    // Parse the message for code blocks
    const parts = parseCodeBlocks(message);

    // If no code blocks found, use original logic
    if (parts.length === 1 && parts[0].type === "text") {
      // Try to parse as JSON one more time for the original TreeNode display
      try {
        const parsed = JSON.parse(message);
        return (
          <div>
            <div className="text-base font-bold">{highlightText(title, searchTerm)}</div>
            <div>
              {TreeNode ? (
                <TreeNode name="" value={parsed} />
              ) : (
                <CodeBlock language="json" code={message} searchTerm={searchTerm} blockId={`${title}-fallback-json`} />
              )}
            </div>
          </div>
        );
      } catch (e) {
        // Fall back to ReactMarkdown for regular text
        return highlightText(
          <div>
            <div className="text-base font-bold">{title}</div>
            <div className="prose prose-sm max-w-none [&_pre]:overflow-x-auto [&_pre]:max-w-full [&_code]:whitespace-pre">
              <ReactMarkdown>{message}</ReactMarkdown>
            </div>
          </div>,
          searchTerm
        );
      }
    }

    // Handle mixed content with code blocks
    return (
      <div>
        <div className="text-base font-bold">{title}</div>
        <div className="mt-2">
          {parts.map((part, index) => {
            if (part.type === "code") {
              return (
                <CodeBlock
                  key={index}
                  language={part.language}
                  code={part.content}
                  searchTerm={searchTerm}
                  blockId={`${title}-${index}`}
                />
              );
            } else {
              return (
                <div key={index} className="prose prose-sm max-w-none [&_pre]:overflow-x-auto [&_pre]:max-w-full [&_code]:whitespace-pre">
                  <ReactMarkdown>{highlightText(part.content, searchTerm)}</ReactMarkdown>
                </div>
              );
            }
          })}
        </div>
      </div>
    );
  };

  return <div className="leading-[1.7]">{renderContent()}</div>;
};

const TrajectoryStepContent = ({ step, searchTerm }) => {
  // Helper function to highlight search terms - no longer used?
  // const highlightText = (text, term) => {
  //   if (!term || !text) return text;

  //   const parts = text.split(new RegExp(`(${term})`, 'gi'));
  //   return parts.map((part, index) =>
  //     part.toLowerCase() === term.toLowerCase() ? (
  //       <span key={index} className="bg-yellow-200">
  //         {part}
  //       </span>
  //     ) : (
  //       part
  //     )
  //   );
  // };

  // Get appropriate icon for each element type
  const getElementIcon = (elementType) => {
    switch (elementType) {
      case "Multimodal data":
        return <Images className="w-4 h-4 text-violet-600 mr-2" />;
      case "Raw text":
        return <LetterText className="w-4 h-4 text-violet-600 mr-2" />;
      case "Thought":
        return <Lightbulb className="w-4 h-4 text-violet-600 mr-2" />;
      case "Observation":
        return <Eye className="w-4 h-4 text-blue-600 mr-2" />;
      case "Action":
        return <Play className="w-4 h-4 text-green-600 mr-2" />;
      case "Artifact":
        return <FileText className="w-4 h-4 text-orange-600 mr-2" />;
      case "Prompt":
        return <Terminal className="w-4 h-4 text-orange-600 mr-2" />;
      case "Rag":
        return <Database className="w-4 h-4 text-orange-600 mr-2" />;
      default:
        return null;
    }
  };

  // Sort the elements by start_index
  const sortedElements = [...(step.elements || [])].sort((a, b) => a.start_index - b.start_index);

  const capitalizeFirstLetter = (string) => {
    if (!string) return string;
    return string.charAt(0).toUpperCase() + string.slice(1).replace("_", " ");
  };

  return (
    <div className="space-y-4 mt-4">
      {sortedElements.map((element, index) => (
        <div key={index} className="p-4 bg-gray-50 rounded border border-gray-200 hover:shadow-sm transition-shadow overflow-hidden">
          <div className="mb-2 text-sm font-medium text-gray-700 flex items-center italic">
            {getElementIcon(capitalizeFirstLetter(element.type))}
            {capitalizeFirstLetter(element.type)}
          </div>
          <div className="leading-[1.7]">
            <EnhancedMessageViewer
              element={element}
              searchTerm={searchTerm}
              Base64ImageViewer={Base64ImageViewer}
              TreeNode={TreeNode}
            />
          </div>
        </div>
      ))}

      {sortedElements.length === 0 && (
        <div className="p-4 text-gray-500 text-sm text-center italic">No elements in this step</div>
      )}
    </div>
  );
};

const TrajectoryStep = ({ step, isActive, searchTerm, onClick, hideTaskPrefixes = false }) => {
  const stepRef = useRef(null);

  // Expose the ref for scroll calculations
  useEffect(() => {
    if (step && stepRef.current) {
      stepRef.current.dataset.stepId = step.task_id || "";
    }
  }, [step]);

  // Check if this step matches the search term
  const matchesSearch =
    searchTerm &&
    step.elements &&
    step.elements.some(
      (element) => element.message && element.message.toLowerCase().includes(searchTerm.toLowerCase())
    );

  // Count elements by type
  const countElementsByType = () => {
    const counts = {
      Thought: 0,
      Observation: 0,
      Action: 0,
      Artifact: 0,
    };

    if (step.elements) {
      step.elements.forEach((element) => {
        if (counts[element.type] !== undefined) {
          counts[element.type]++;
        }
      });
    }

    return counts;
  };

  const elementCounts = countElementsByType();
  const totalElements = step.elements ? step.elements.length : 0;

  // Get type indicators based on what's in the step
  const getTypeIndicators = () => {
    const indicators = [];

    if (elementCounts.Thought > 0) {
      indicators.push(
        <div key="thoughts" className="flex items-center mr-3" title="Contains thoughts">
          <Lightbulb className="w-3 h-3 text-violet-600 mr-1" />
          <span className="text-xs">{elementCounts.Thought}</span>
        </div>
      );
    }

    if (elementCounts.Observation > 0) {
      indicators.push(
        <div key="observations" className="flex items-center mr-3" title="Contains observations">
          <Eye className="w-3 h-3 text-blue-600 mr-1" />
          <span className="text-xs">{elementCounts.Observation}</span>
        </div>
      );
    }

    if (elementCounts.Action > 0) {
      indicators.push(
        <div key="actions" className="flex items-center mr-3" title="Contains actions">
          <Play className="w-3 h-3 text-green-600 mr-1" />
          <span className="text-xs">{elementCounts.Action}</span>
        </div>
      );
    }

    if (elementCounts.Artifact > 0) {
      indicators.push(
        <div key="artifacts" className="flex items-center mr-3" title="Contains artifacts">
          <FileText className="w-3 h-3 text-orange-600 mr-1" />
          <span className="text-xs">{elementCounts.Artifact}</span>
        </div>
      );
    }

    return indicators;
  };

  // Format the task name for display
  const displayTaskName = formatTaskName(step.task_name, hideTaskPrefixes);

  return (
    <div
      ref={stepRef}
      className={`
        mb-6 bg-white rounded-lg border border-gray-200 p-6
        ${isActive ? "border-l-4 border-l-blue-500 shadow-md" : ""} 
        ${matchesSearch ? "ring-2 ring-yellow-400" : ""}
        ${!searchTerm || matchesSearch ? "" : "opacity-50"}
        transition-all duration-200 hover:shadow-md cursor-pointer
      `}
      onClick={onClick}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex-grow">
          <h3 className="text-lg font-medium mb-1">{displayTaskName}</h3>
          <div className="text-xs text-gray-500 flex items-center">
            <span className="mr-4">Task ID: {step.task_id.substring(0, 8)}...</span>
            <div className="flex items-center">{getTypeIndicators()}</div>
          </div>
        </div>
        <Tag type={isActive ? "blue" : totalElements > 0 ? "green" : "gray"} className="ml-2 shrink-0">
          {isActive ? "Current" : totalElements > 0 ? `${totalElements} items` : "Empty"}
        </Tag>
      </div>

      {/* Always show content - no conditional rendering */}
      <TrajectoryStepContent step={step} searchTerm={searchTerm} />
    </div>
  );
};

const TrajectoryViewer = ({ data, handleTaskClick, hideTaskPrefixes = false }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [searchTerm, setSearchTerm] = useState("");
  const [filteredSteps, setFilteredSteps] = useState([]);
  const scrollContainerRef = useRef(null);

  // Transform the data structure if needed
  const transformData = (rawData) => {
    if (!rawData) return [];

    return rawData.map((step) => {
      // If the step already has elements array, just return it as is
      if (step.elements) return step;

      // Otherwise, transform the old format to new format
      const elements = [];

      if (step.thoughts) {
        step.thoughts.forEach((thought, index) => {
          elements.push({
            type: "Thought",
            message: thought,
            start_index: index, // Default ordering if no start_index provided
          });
        });
      }

      if (step.observations) {
        step.observations.forEach((observation, index) => {
          elements.push({
            type: "Observation",
            message: observation,
            start_index: index + 1000, // Default ordering if no start_index provided
          });
        });
      }

      if (step.actions) {
        step.actions.forEach((action, index) => {
          elements.push({
            type: "Action",
            message: action,
            start_index: index + 2000, // Default ordering if no start_index provided
          });
        });
      }

      if (step.artifacts) {
        step.artifacts.forEach((artifact, index) => {
          elements.push({
            type: "Artifact",
            message: typeof artifact === "string" ? artifact : JSON.stringify(artifact, null, 2),
            start_index: index + 3000, // Default ordering if no start_index provided
          });
        });
      }

      return {
        ...step,
        elements,
      };
    });
  };

  useEffect(() => {
    const transformedData = transformData(data);

    if (!transformedData || transformedData.length === 0) {
      setFilteredSteps([]);
      return;
    }

    if (searchTerm) {
      const filtered = transformedData.filter(
        (step) =>
          step.elements &&
          step.elements.some(
            (element) => element.message && element.message.toLowerCase().includes(searchTerm.toLowerCase())
          )
      );
      setFilteredSteps(filtered);

      // Reset current step if it's now out of bounds
      if (filtered.length > 0 && currentStep >= filtered.length) {
        setCurrentStep(0);
      }
    } else {
      setFilteredSteps(transformedData);
    }
  }, [data, searchTerm, currentStep]);

  // Set up scroll listener to update current step based on visible area
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const containerRect = container.getBoundingClientRect();
      const containerTop = containerRect.top;

      // Find the step that's closest to the top of the container
      const stepElements = container.querySelectorAll("[data-step-id]");
      let closestStepIndex = 0;
      let smallestDistance = Infinity;

      stepElements.forEach((element, index) => {
        const rect = element.getBoundingClientRect();
        const distance = Math.abs(rect.top - containerTop);

        // Only consider steps that are at least partially visible
        if (rect.bottom > containerTop && distance < smallestDistance) {
          smallestDistance = distance;
          closestStepIndex = index;
        }
      });

      if (closestStepIndex !== currentStep) {
        setCurrentStep(closestStepIndex);
        handleStepClick(closestStepIndex);
      }
    };

    // Throttle scroll events for performance
    let timeoutId;
    const throttledHandleScroll = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(handleScroll, 100);
    };

    container.addEventListener("scroll", throttledHandleScroll);
    return () => {
      container.removeEventListener("scroll", throttledHandleScroll);
      clearTimeout(timeoutId);
    };
  }, [filteredSteps.length, currentStep]);

  const scrollToStep = (stepIndex) => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const stepElements = container.querySelectorAll("[data-step-id]");
    const targetElement = stepElements[stepIndex];

    if (targetElement) {
      const containerRect = container.getBoundingClientRect();
      const elementRect = targetElement.getBoundingClientRect();

      // Calculate scroll position to bring element to top of container
      const scrollTop = container.scrollTop + elementRect.top - containerRect.top;

      container.scrollTo({
        top: scrollTop,
        behavior: "smooth",
      });
    }
  };

  const handleStepClickAndScroll = (index) => {
    setCurrentStep(index);
    scrollToStep(index);
    handleStepClick(index);
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      const newStep = currentStep - 1;
      setCurrentStep(newStep);
      scrollToStep(newStep);
      handleStepClick(newStep);
    }
  };

  const handleNext = () => {
    if (currentStep < filteredSteps.length - 1) {
      const newStep = currentStep + 1;
      setCurrentStep(newStep);
      scrollToStep(newStep);
      handleStepClick(newStep);
    }
  };

  const handleSearch = (term) => {
    setSearchTerm(term);
    setCurrentStep(0); // Reset to first step when searching
  };

  const handleStepClick = (index) => {
    const step = filteredSteps[index];

    // Find the corresponding task using task_id and select it
    if (handleTaskClick && step && step.task) {
      handleTaskClick(step.task);
    }
  };

  if (!filteredSteps || filteredSteps.length === 0) {
    return (
      <div
        className="p-8 bg-white rounded-lg border border-gray-200 flex flex-col items-center justify-center"
        style={{ minHeight: "400px" }}
      >
        <PanelLeftClose className="w-12 h-12 text-gray-300 mb-4" />
        <div className="text-gray-600 text-lg font-medium">No trajectory data available</div>
        <div className="text-gray-500 text-sm mt-2 max-w-md text-center">
          Trajectory data will appear here when available in the trace. Trajectory steps show the agent's thoughts,
          observations, and actions during execution.
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* Fixed header with navigation and search */}
      <div className="bg-white p-2 rounded-lg border border-gray-200 mb-2 sticky top-0 z-10">
        <div className="flex flex-col md:flex-row md:justify-between md:items-center">
          <StepNavigation
            currentStep={currentStep}
            totalSteps={filteredSteps.length}
            onPrev={handlePrev}
            onNext={handleNext}
          />

          <SearchBar onSearch={handleSearch} />
        </div>

        {searchTerm && (
          <div className="mt-4">
            <InlineNotification
              kind="info"
              title={
                filteredSteps.length > 0 ? `Found ${filteredSteps.length} matching steps` : "No matching steps found"
              }
              subtitle={
                filteredSteps.length > 0
                  ? `Showing results for "${searchTerm}"`
                  : `No steps match your search term "${searchTerm}"`
              }
              onClose={() => {
                setSearchTerm("");
                handleSearch("");
              }}
            />
          </div>
        )}
      </div>

      {/* Scrollable steps container */}
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 pt-0">
        <div className="space-y-4">
          {filteredSteps.map((step, index) => (
            <TrajectoryStep
              key={index}
              step={step}
              isActive={index === currentStep}
              searchTerm={searchTerm}
              onClick={() => handleStepClickAndScroll(index)}
              hideTaskPrefixes={hideTaskPrefixes}
            />
          ))}

          {filteredSteps.length === 0 && searchTerm && (
            <div className="p-8 text-center bg-white rounded-lg border border-gray-200">
              <div className="text-gray-500">No steps match your search term "{searchTerm}"</div>
              <Button
                type="tertiary"
                className="mt-4"
                onClick={() => {
                  setSearchTerm("");
                  handleSearch("");
                }}
              >
                Clear Search
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TrajectoryViewer;
