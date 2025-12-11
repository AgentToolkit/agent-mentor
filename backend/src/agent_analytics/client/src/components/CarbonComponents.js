// Button styles depending on type
const getButtonStyles = (type = "primary", size = "default", isFullWidth = false) => {
  const baseStyles = `
    h-${size === "small" ? "8" : "10"} 
    px-4 
    ${isFullWidth ? "w-full" : ""} 
    transition-colors 
    border-0 
    outline-none
    font-normal
    text-sm
    focus:outline-2
    focus:outline-offset-[-2px]
    focus:outline
    focus:outline-[#0f62fe]
    disabled:cursor-not-allowed
  `;

  const typeStyles = {
    primary: `bg-[#0f62fe] text-white hover:bg-[#0353e9] active:bg-[#002d9c] disabled:bg-[#c6c6c6] disabled:text-[#8d8d8d]`,
    secondary: `bg-[#393939] text-white hover:bg-[#4c4c4c] active:bg-[#6f6f6f] disabled:bg-[#c6c6c6] disabled:text-[#8d8d8d]`,
    tertiary: `bg-transparent text-[#0f62fe] border border-[#0f62fe] hover:bg-[#e5e5e5] disabled:border-[#c6c6c6] disabled:text-[#8d8d8d]`,
    ghost: `bg-transparent text-[#0f62fe] hover:bg-[#e5e5e5] disabled:text-[#8d8d8d]`,
    danger: `bg-[#da1e28] text-white hover:bg-[#bc1a22] active:bg-[#a51920] disabled:bg-[#c6c6c6] disabled:text-[#8d8d8d]`,
  };

  return `${baseStyles} ${typeStyles[type] || typeStyles.primary}`;
};

// Button Component
export const Button = ({
  children,
  type = "primary",
  size = "default",
  isFullWidth = false,
  className = "",
  ...props
}) => {
  const buttonStyles = getButtonStyles(type, size, isFullWidth);

  return (
    <button className={`${buttonStyles} ${className}`} {...props}>
      {children}
    </button>
  );
};

// Input Component
export const Input = ({ className = "", ...props }) => {
  return (
    <input
      className={`
        h-10 
        px-4 
        border-0
        border-b-2
        border-b-[#8d8d8d] 
        text-[#161616] 
        bg-[#f4f4f4]
        outline-none
        focus:outline-none
        focus:border-b-[#0f62fe]
        disabled:bg-[#e0e0e0]
        disabled:text-[#a8a8a8]
        disabled:cursor-not-allowed
        placeholder:text-[#6f6f6f]
        text-sm
        transition-colors
        ${className}
      `}
      {...props}
    />
  );
};

// Checkbox Component
export const Checkbox = ({ className = "", id, label, ...props }) => {
  return (
    <div className="flex items-center">
      <input
        type="checkbox"
        id={id}
        className={`
          appearance-none
          h-4
          w-4
          border
          border-[#8d8d8d]
          bg-white
          relative
          focus:outline
          focus:outline-2
          focus:outline-[#0f62fe]
          focus:outline-offset-[-2px]
          cursor-pointer
          checked:bg-white
          checked:border-[#0f62fe]
          after:absolute
          after:content-['']
          after:hidden
          checked:after:block
          after:left-[5px]
          after:top-[1px]
          after:w-[4px]
          after:h-[10px]
          after:border-r-2
          after:border-b-2
          after:border-[#0f62fe]
          after:rotate-45
          ${className}
        `}
        {...props}
      />
      {label && (
        <label htmlFor={id} className="ml-2 text-sm text-[#161616] cursor-pointer">
          {label}
        </label>
      )}
    </div>
  );
};

// Tag Component
export const Tag = ({ children, type = "default", className = "", icon = null, ...props }) => {
  const typeStyles = {
    default: "bg-[#e0e0e0] text-[#393939]",
    red: "bg-[#ffd7d9] text-[#da1e28]",
    green: "bg-[#defbe6] text-[#24a148]",
    blue: "bg-[#d0e2ff] text-[#0043ce]",
    purple: "bg-[#e8daff] text-[#6929c4]",
    teal: "bg-[#d9fbfb] text-[#0072c3]",
    gray: "bg-[#f4f4f4] text-[#525252]",
  };

  return (
    <span
      className={`
        inline-flex
        items-center
        h-6
        px-2
        text-xs
        font-medium
        ${typeStyles[type] || typeStyles.default}
        ${className}
      `}
      {...props}
    >
      {icon && <span className="mr-1.5">{icon}</span>}
      {children}
    </span>
  );
};

// Table Component
export const Table = ({ children, className = "", ...props }) => {
  return (
    <table className={`w-full border-collapse ${className}`} {...props}>
      {children}
    </table>
  );
};

export const TableHead = ({ children, className = "", ...props }) => {
  return (
    <thead className={`bg-[#f4f4f4] ${className}`} {...props}>
      {children}
    </thead>
  );
};

export const TableBody = ({ children, className = "", ...props }) => {
  return (
    <tbody className={`bg-white ${className}`} {...props}>
      {children}
    </tbody>
  );
};

export const TableRow = ({ children, className = "", isSelected = false, isHoverable = true, ...props }) => {
  return (
    <tr
      className={`
        ${isSelected ? "bg-[#e5f0ff]" : ""}
        ${isHoverable ? "hover:bg-[#f4f4f4]" : ""}
        ${className}
      `}
      {...props}
    >
      {children}
    </tr>
  );
};

export const TableCell = ({ children, className = "", ...props }) => {
  return (
    <td
      className={`
        px-4
        py-3
        border-b
        border-[#e0e0e0]
        text-sm
        ${className}
      `}
      {...props}
    >
      {children}
    </td>
  );
};

export const TableHeader = ({ children, className = "", ...props }) => {
  return (
    <th
      className={`
        px-4
        py-3
        border-b
        border-[#e0e0e0]
        text-left
        text-xs
        font-medium
        text-[#525252]
        uppercase
        tracking-wider
        ${className}
      `}
      {...props}
    >
      {children}
    </th>
  );
};

// Modal Components
export const Modal = ({ children, className = "", ...props }) => {
  return (
    <div
      className={`
        bg-white
        border
        border-[#e0e0e0]
        shadow-lg
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
};

export const ModalHeader = ({ title, onClose, className = "", ...props }) => {
  return (
    <div
      className={`
        px-4
        py-3
        border-b
        border-[#e0e0e0]
        flex
        justify-between
        items-center
        ${className}
      `}
      {...props}
    >
      <h2 className="text-xl font-normal text-[#161616]">{title}</h2>
      {onClose && (
        <button onClick={onClose} className="text-[#525252] hover:text-[#161616] focus:outline-none">
          <svg width="20" height="20" viewBox="0 0 32 32" fill="currentColor">
            <path d="M24 9.4L22.6 8 16 14.6 9.4 8 8 9.4 14.6 16 8 22.6 9.4 24 16 17.4 22.6 24 24 22.6 17.4 16 24 9.4z"></path>
          </svg>
        </button>
      )}
    </div>
  );
};

export const ModalBody = ({ children, className = "", ...props }) => {
  return (
    <div className={`p-4 ${className}`} {...props}>
      {children}
    </div>
  );
};

export const ModalFooter = ({ children, className = "", ...props }) => {
  return (
    <div
      className={`
        p-4
        border-t
        border-[#e0e0e0]
        flex
        justify-end
        gap-4
        ${className}
      `}
      {...props}
    >
      {children}
    </div>
  );
};

// Loading Component
export const Loading = ({ withOverlay = false, description = "Loading", className = "", ...props }) => {
  const Spinner = () => (
    <div
      className={`
        flex
        flex-col
        items-center
        justify-center
        ${className}
      `}
      {...props}
    >
      <div className="relative h-10 w-10">
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-[#e0e0e0] border-t-[#0f62fe]"></div>
      </div>
      {description && <p className="mt-2 text-sm text-[#525252]">{description}</p>}
    </div>
  );

  if (withOverlay) {
    return (
      <div className="fixed inset-0 bg-white bg-opacity-70 flex items-center justify-center z-50">
        <Spinner />
      </div>
    );
  }

  return <Spinner />;
};

// Notification Component
export const InlineNotification = ({ title, subtitle, kind = "info", onClose, className = "", ...props }) => {
  const kindStyles = {
    error: "bg-[#fff1f1] border-l-[#da1e28] text-[#da1e28]",
    info: "bg-[#edf5ff] border-l-[#0043ce] text-[#0043ce]",
    success: "bg-[#defbe6] border-l-[#24a148] text-[#24a148]",
    warning: "bg-[#fdf6dd] border-l-[#f1c21b] text-[#8a6a00]",
  };

  return (
    <div
      className={`
        border-l-4
        p-4
        ${kindStyles[kind] || kindStyles.info}
        ${className}
      `}
      role="alert"
      {...props}
    >
      <div className="flex items-start">
        <div className="flex-grow">
          {title && <h3 className="text-sm font-medium">{title}</h3>}
          {subtitle && <p className="text-sm mt-1">{subtitle}</p>}
        </div>
        {onClose && (
          <button onClick={onClose} className="ml-4 text-current hover:text-[#161616]">
            <svg width="16" height="16" viewBox="0 0 32 32" fill="currentColor">
              <path d="M24 9.4L22.6 8 16 14.6 9.4 8 8 9.4 14.6 16 8 22.6 9.4 24 16 17.4 22.6 24 24 22.6 17.4 16 24 9.4z"></path>
            </svg>
          </button>
        )}
      </div>
    </div>
  );
};

// Stack Container
export const Stack = ({ children, direction = "column", spacing = 4, className = "", ...props }) => {
  const directionClass = direction === "row" ? "flex-row" : "flex-col";
  const spacingClass = `gap-${spacing}`;

  return (
    <div className={`flex ${directionClass} ${spacingClass} ${className}`} {...props}>
      {children}
    </div>
  );
};

// Divider
export const Divider = ({ className = "", ...props }) => {
  return <hr className={`border-t border-[#e0e0e0] my-4 ${className}`} {...props} />;
};

export default {
  Button,
  Input,
  Checkbox,
  Tag,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableHeader,
  Modal,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Loading,
  InlineNotification,
  Stack,
  Divider,
};
