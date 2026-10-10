import React from 'react';
import { Loader2 } from 'lucide-react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  loading?: boolean;
  leftIcon?: React.ReactNode;
  leadingIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  trailingIcon?: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      isLoading = false,
      loading,
      leftIcon,
      leadingIcon,
      rightIcon,
      trailingIcon,
      children,
      className = '',
      disabled,
      ...props
    },
    ref
  ) => {
    const isActuallyLoading = loading ?? isLoading;
    const resolvedLeftIcon = leadingIcon ?? leftIcon;
    const resolvedRightIcon = trailingIcon ?? rightIcon;

    const baseClasses =
      'inline-flex items-center justify-center font-semibold rounded-btn transition-all duration-150 active:scale-[0.98] disabled:opacity-50 disabled:pointer-events-none disabled:active:scale-100 select-none focus-visible:ring-2 focus-visible:ring-focus-ring outline-none';

    const sizeClasses = {
      sm: 'text-xs px-3 py-1.5 min-h-[36px] md:min-h-[32px] gap-1.5',
      md: 'text-sm px-4 py-2 min-h-[40px] gap-2',
      lg: 'text-base px-5 py-2.5 min-h-[44px] gap-2.5',
    }[size];

    const variantClasses = {
      primary:
        'bg-accent hover:bg-accent-hover text-accent-contrast shadow-xs transition-colors',
      secondary:
        'bg-surface-2 hover:bg-border text-text border border-border shadow-xs hover:border-border-subtle',
      ghost:
        'bg-transparent hover:bg-surface-2 text-text-muted hover:text-text',
      danger:
        'bg-danger text-white shadow-xs hover:bg-danger/90 active:bg-danger/95',
    }[variant];

    return (
      <button
        ref={ref}
        disabled={disabled || isActuallyLoading}
        className={`${baseClasses} ${sizeClasses} ${variantClasses} ${className}`}
        {...props}
      >
        {isActuallyLoading ? (
          <Loader2 className="animate-spin shrink-0" size={size === 'sm' ? 14 : 16} aria-hidden="true" />
        ) : (
          resolvedLeftIcon && <span className="shrink-0">{resolvedLeftIcon}</span>
        )}
        <span>{children}</span>
        {!isActuallyLoading && resolvedRightIcon && <span className="shrink-0">{resolvedRightIcon}</span>}
      </button>
    );
  }
);

Button.displayName = 'Button';
