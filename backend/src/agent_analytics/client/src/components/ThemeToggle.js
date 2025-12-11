import React from 'react';
import { useTheme } from 'next-themes';
import { Sun, Moon, Monitor } from 'lucide-react';

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Theme</label>
      <div className="flex items-center gap-2">
        <button
          onClick={() => setTheme('light')}
          className={`flex items-center gap-2 px-4 py-2 rounded transition-colors ${
            theme === 'light'
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
          aria-label="Light mode"
          title="Light mode"
        >
          <Sun size={16} />
          <span className="text-sm">Light</span>
        </button>
        <button
          onClick={() => setTheme('dark')}
          className={`flex items-center gap-2 px-4 py-2 rounded transition-colors ${
            theme === 'dark'
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
          aria-label="Dark mode"
          title="Dark mode"
        >
          <Moon size={16} />
          <span className="text-sm">Dark</span>
        </button>
        <button
          onClick={() => setTheme('system')}
          className={`flex items-center gap-2 px-4 py-2 rounded transition-colors ${
            theme === 'system'
              ? 'bg-blue-100 dark:bg-blue-900 text-blue-700 dark:text-blue-300 border border-blue-300 dark:border-blue-700'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
          }`}
          aria-label="System mode"
          title="System mode"
        >
          <Monitor size={16} />
          <span className="text-sm">System</span>
        </button>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">Choose your preferred color theme</p>
    </div>
  );
}
