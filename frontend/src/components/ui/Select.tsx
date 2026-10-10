import React from 'react';
import { ChevronDown } from 'lucide-react';

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string | null;
  helperText?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, helperText, id, className = '', children, disabled, ...props }, ref) => {
    const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label htmlFor={selectId} className="block text-xs font-semibold text-text">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          <select
            ref={ref}
            id={selectId}
            disabled={disabled}
            className={`w-full appearance-none rounded-input border bg-surface py-2 pl-3.5 pr-9 text-sm text-text transition-colors outline-none focus-visible:ring-2 focus-visible:ring-focus-ring disabled:opacity-50 disabled:bg-surface-2 min-h-[40px] cursor-pointer ${
              error
                ? 'border-danger focus-visible:border-danger'
                : 'border-border focus:border-primary hover:border-border-subtle'
            } ${className}`}
            {...props}
          >
            {children}
          </select>
          <div className="pointer-events-none absolute right-3 flex items-center text-text-muted">
            <ChevronDown size={16} aria-hidden="true" />
          </div>
        </div>
        {error ? (
          <p className="text-xs text-danger font-medium">{error}</p>
        ) : helperText ? (
          <p className="text-xs text-text-muted">{helperText}</p>
        ) : null}
      </div>
    );
  }
);

Select.displayName = 'Select';
