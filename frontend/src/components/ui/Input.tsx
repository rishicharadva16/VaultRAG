import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  leftIcon?: React.ReactNode;
  rightAction?: React.ReactNode;
  helperText?: string;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, leftIcon, rightAction, helperText, id, className = '', disabled, ...props }, ref) => {
    const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

    return (
      <div className="w-full space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-xs font-semibold text-text">
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {leftIcon && (
            <div className="pointer-events-none absolute left-3 flex items-center text-text-muted">
              {leftIcon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            disabled={disabled}
            className={`w-full rounded-input border bg-surface py-2 text-sm text-text placeholder:text-text-muted transition-colors outline-none focus-visible:ring-2 focus-visible:ring-focus-ring disabled:opacity-50 disabled:bg-surface-2 min-h-[40px] ${
              leftIcon ? 'pl-9' : 'pl-3.5'
            } ${rightAction ? 'pr-10' : 'pr-3.5'} ${
              error
                ? 'border-danger focus-visible:border-danger'
                : 'border-border focus:border-primary hover:border-border-subtle'
            } ${className}`}
            {...props}
          />
          {rightAction && (
            <div className="absolute right-2.5 flex items-center">{rightAction}</div>
          )}
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

Input.displayName = 'Input';
