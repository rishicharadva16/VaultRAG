import React from 'react';

export interface PageHeaderProps {
  title: string;
  subtitle?: string | React.ReactNode;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  breadcrumb?: string;
  className?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  icon,
  actions,
  breadcrumb,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-5 mb-6 ${className}`}
    >
      <div className="space-y-1">
        {breadcrumb && (
          <div className="text-xs font-semibold uppercase tracking-wider text-accent">
            {breadcrumb}
          </div>
        )}
        <div className="flex items-center gap-3">
          {icon && (
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-btn bg-accent text-accent-contrast shadow-xs">
              {icon}
            </div>
          )}
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
            {title}
          </h1>
        </div>
        {subtitle && (
          <p className="text-xs sm:text-sm text-text-muted leading-relaxed max-w-2xl">
            {subtitle}
          </p>
        )}
      </div>

      {actions && <div className="flex items-center gap-2.5 shrink-0">{actions}</div>}
    </div>
  );
};
