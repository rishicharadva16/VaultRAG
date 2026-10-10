import React from 'react';

export interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  label: string;
  value: string | number;
  subValue?: string;
  icon?: React.ReactNode;
  iconBg?: string;
  sparklineData?: number[];
  sparklineColor?: string;
  trend?: {
    direction: 'up' | 'down' | 'neutral';
    text: string;
  };
  testId?: string;
  className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  subValue,
  icon,
  iconBg = 'bg-primary-soft text-accent',
  sparklineData,
  sparklineColor = '#2563eb',
  trend,
  testId,
  className = '',
  ...rest
}) => {
  // Render small inline-SVG sparkline if data provided
  const renderSparkline = () => {
    if (!sparklineData || sparklineData.length < 2) return null;
    const min = Math.min(...sparklineData);
    const max = Math.max(...sparklineData);
    const range = max - min || 1;
    const height = 28;
    const width = 64;
    const step = width / (sparklineData.length - 1);

    const points = sparklineData
      .map((val, idx) => {
        const x = idx * step;
        const y = height - ((val - min) / range) * (height - 6) - 3;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');

    return (
      <svg
        width={width}
        height={height}
        className="overflow-visible shrink-0"
        aria-hidden="true"
      >
        <polyline
          fill="none"
          stroke={sparklineColor}
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          points={points}
        />
      </svg>
    );
  };

  return (
    <div
      data-testid={testId || (rest as Record<string, unknown>)['data-testid'] as string | undefined}
      className={`rounded-card border border-border bg-surface p-4 sm:p-5 shadow-xs transition-colors hover:border-border-subtle ${className}`}
      {...rest}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1 min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-text-muted truncate">
            {label}
          </p>
          <div className="flex items-baseline gap-2">
            <span className="text-2xl sm:text-3xl font-bold tracking-tight text-text">
              {value}
            </span>
            {subValue && (
              <span className="text-xs text-text-muted font-medium">{subValue}</span>
            )}
          </div>
        </div>

        {icon && (
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-btn shadow-xs ${iconBg}`}
          >
            {icon}
          </div>
        )}
      </div>

      {(sparklineData || trend) && (
        <div className="mt-3 flex items-center justify-between border-t border-border-subtle pt-2.5">
          {trend && (
            <div className="flex items-center gap-1 text-xs">
              <span
                className={
                  trend.direction === 'up'
                    ? 'text-success font-medium'
                    : trend.direction === 'down'
                    ? 'text-danger font-medium'
                    : 'text-text-muted'
                }
              >
                {trend.text}
              </span>
            </div>
          )}
          {renderSparkline()}
        </div>
      )}
    </div>
  );
};
