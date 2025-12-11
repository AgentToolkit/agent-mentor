// Carbon Design System color palette and styling variables
// Based on Carbon Design System https://carbondesignsystem.com/

export const colors = {
  // Primary colors
  primary: '#0f62fe', // Carbon Blue 60
  primaryHover: '#0353e9', // Carbon Blue 70
  primaryActive: '#002d9c', // Carbon Blue 80

  // Supporting colors
  secondary: '#393939', // Carbon Gray 80
  secondaryHover: '#4c4c4c', // Carbon Gray 70
  secondaryActive: '#6f6f6f', // Carbon Gray 60

  // UI Background colors
  background: '#f4f4f4', // Carbon Gray 10
  backgroundHover: '#e0e0e0', // Carbon Gray 20

  // Text colors
  text: {
    primary: '#161616', // Carbon Gray 100
    secondary: '#525252', // Carbon Gray 70
    helper: '#6f6f6f', // Carbon Gray 60
    error: '#da1e28', // Carbon Red 60
    inverse: '#ffffff', // White
    disabled: '#a8a8a8', // Carbon Gray 40
  },

  // Status colors
  status: {
    error: '#da1e28', // Carbon Red 60
    success: '#24a148', // Carbon Green 60
    warning: '#f1c21b', // Carbon Yellow 30
    info: '#0043ce', // Carbon Blue 70
  },

  // Brand and UI element colors
  ui: {
    border: '#8d8d8d', // Carbon Gray 50
    borderLight: '#e0e0e0', // Carbon Gray 20
    focus: '#0f62fe', // Carbon Blue 60
    page: '#ffffff', // White
    overlay: 'rgba(22, 22, 22, 0.5)', // Gray 100 with 50% opacity
    disabled: '#c6c6c6', // Carbon Gray 30
  },
};

export const spacing = {
  xs: '0.25rem', // 4px
  sm: '0.5rem', // 8px
  md: '1rem', // 16px
  lg: '1.5rem', // 24px
  xl: '2rem', // 32px
  xxl: '3rem', // 48px
};

export const typography = {
  fontFamily: "'IBM Plex Sans', 'Helvetica Neue', Arial, sans-serif",
  sizes: {
    xs: '0.75rem', // 12px
    sm: '0.875rem', // 14px - Body
    md: '1rem', // 16px - Heading 4
    lg: '1.125rem', // 18px - Heading 3
    xl: '1.25rem', // 20px - Heading 2
    xxl: '1.5rem', // 24px - Heading 1
    xxxl: '2rem', // 32px - Display 1
  },
  weights: {
    light: 300,
    regular: 400,
    medium: 500,
    semibold: 600,
  },
};

export const layout = {
  borderRadius: '0', // Carbon uses square corners
  inputHeight: '2.5rem', // 40px
  buttonHeight: '2.5rem', // 40px
  smallButtonHeight: '2rem', // 32px
  boxShadow: '0 2px 6px rgba(0, 0, 0, 0.2)',
  focus: {
    border: `2px solid ${colors.ui.focus}`,
    boxShadow: 'none',
  },
};

export const zIndex = {
  modal: 9000,
  overlay: 8000,
  dropdown: 7000,
  header: 6000,
  footer: 5000,
  tooltip: 9010,
};

export const transitions = {
  standard: 'all 0.2s cubic-bezier(0.2, 0, 0.38, 0.9)',
  entrance: 'all 0.3s cubic-bezier(0, 0, 0.38, 0.9)',
  exit: 'all 0.2s cubic-bezier(0.2, 0, 1, 0.9)',
};

// Helper CSS classes (tailwind like but Carbon styled)
export const helpers = {
  button: {
    primary: `
        bg-[${colors.primary}] 
        text-white 
        hover:bg-[${colors.primaryHover}] 
        active:bg-[${colors.primaryActive}]
        focus:outline-none 
        focus:ring-2 
        focus:ring-[${colors.ui.focus}] 
        focus:ring-offset-2
        disabled:bg-[${colors.ui.disabled}]
        disabled:text-[${colors.text.disabled}]
        disabled:cursor-not-allowed
        font-normal
        transition-colors
        border-0
      `,
    secondary: `
        bg-[${colors.secondary}]
        text-white
        hover:bg-[${colors.secondaryHover}]
        active:bg-[${colors.secondaryActive}]
        focus:outline-none
        focus:ring-2
        focus:ring-[${colors.ui.focus}]
        focus:ring-offset-2
        disabled:bg-[${colors.ui.disabled}]
        disabled:text-[${colors.text.disabled}]
        disabled:cursor-not-allowed
        font-normal
        transition-colors
        border-0
      `,
    tertiary: `
        bg-transparent
        text-[${colors.primary}]
        hover:bg-[${colors.backgroundHover}]
        active:bg-[${colors.background}]
        border border-[${colors.primary}]
        focus:outline-none
        focus:ring-2
        focus:ring-[${colors.ui.focus}]
        focus:ring-offset-2
        disabled:text-[${colors.text.disabled}]
        disabled:border-[${colors.ui.disabled}]
        disabled:cursor-not-allowed
        font-normal
        transition-colors
      `,
    ghost: `
        bg-transparent
        text-[${colors.primary}]
        hover:bg-[${colors.backgroundHover}]
        active:bg-[${colors.background}]
        border-0
        focus:outline-none
        focus:ring-2
        focus:ring-[${colors.ui.focus}]
        focus:ring-offset-2
        disabled:text-[${colors.text.disabled}]
        disabled:cursor-not-allowed
        font-normal
        transition-colors
      `,
  },
  input: `
      h-[${layout.inputHeight}]
      border border-[${colors.ui.border}]
      focus:outline-none
      focus:border-[${colors.ui.focus}]
      focus:ring-1
      focus:ring-[${colors.ui.focus}]
      disabled:bg-[${colors.ui.disabled}]
      disabled:text-[${colors.text.disabled}]
      disabled:cursor-not-allowed
      text-[${colors.text.primary}]
      bg-white
      p-0
      px-${spacing.md}
      transition-colors
    `,
  modal: `
      border border-[${colors.ui.borderLight}]
      bg-white
      shadow-md
    `,
  tag: `
      inline-flex
      items-center
      px-${spacing.sm}
      py-${spacing.xs}
      rounded-full
      text-${typography.sizes.xs}
      font-medium
    `,
};

export default {
  colors,
  spacing,
  typography,
  layout,
  zIndex,
  transitions,
  helpers,
};
