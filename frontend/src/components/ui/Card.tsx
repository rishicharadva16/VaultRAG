import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverLift?: boolean;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ hoverLift = false, className = '', children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={`rounded-card border border-border bg-surface p-5 shadow-sm transition-all duration-150 ${
          hoverLift ? 'hover:-translate-y-0.5 hover:shadow-md hover:border-border-subtle' : ''
        } ${className}`}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';
