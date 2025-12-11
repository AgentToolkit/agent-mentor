import React from "react";

/**
 * A simplified BreadcrumbNavigation component that shows only the current level name.
 */
const BreadcrumbNavigation = ({
  navigationPath,
  navigateToLevel, // Prop kept for API compatibility, but no longer used
  colors,
}) => {
  const isRoot = navigationPath.length === 0;
  const currentLevelName = isRoot
    ? "Root"
    : navigationPath[navigationPath.length - 1].name;

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center", // Center the title
        width: "100%",
        position: "relative",
        zIndex: 10,
        backgroundColor: colors.breadcrumbBg,
        borderBottom: `1px solid ${colors.tileBorder}`,
        padding: "0.75rem 1rem",
        borderTopLeftRadius: "4px",
        borderTopRightRadius: "4px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}
    >
      {/* Current level name (centered) */}
      <div
        className="current-level-title"
        style={{
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
          fontWeight: "600",
          color: colors.text,
          fontSize: "1.1rem",
        }}
      >
        {currentLevelName.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())}
      </div>
    </div>
  );
};

export default BreadcrumbNavigation;