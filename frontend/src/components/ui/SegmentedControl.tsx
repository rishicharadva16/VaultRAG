import React from 'react';

export interface SegmentOption<T extends string = string> {
  value: T;
  label: React.ReactNode;
  icon?: React.ReactNode;
  count?: number;
  testId?: string;
}

export interface SegmentedControlProps<T extends string = string> {
  options: SegmentOption<T>[];
  value: T;
  onChange: (val: T) => void;
  className?: string;
}

export function SegmentedControl<T extends string = string>({
  options,
  value,
  onChange,
  className = '',
}: SegmentedControlProps<T>) {
  return (
    <div
      role="tablist"
      className={`inline-flex items-center rounded-btn border border-border bg-surface-2 p-1 gap-1 ${className}`}
    >
      {options.map((opt) => {
        const isActive = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            data-testid={opt.testId}
            onClick={() => onChange(opt.value)}
            className={`inline-flex items-center gap-2 rounded-[9px] px-3 py-1.5 text-xs font-semibold transition-all duration-150 min-h-[34px] sm:min-h-[30px] outline-none focus-visible:ring-2 focus-visible:ring-focus-ring select-none ${
              isActive
                ? 'bg-surface text-text shadow-sm border border-border/60'
                : 'text-text-muted hover:text-text hover:bg-surface/50'
            }`}
          >
            {opt.icon && <span className="shrink-0">{opt.icon}</span>}
            <span>{opt.label}</span>
            {opt.count !== undefined && (
              <span
                className={`ml-1 rounded-badge px-1.5 py-0.2 text-[10px] font-bold ${
                  isActive
                    ? 'bg-primary-soft text-primary'
                    : 'bg-surface border border-border text-text-muted'
                }`}
              >
                {opt.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
