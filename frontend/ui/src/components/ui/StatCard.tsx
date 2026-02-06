/**
 * Card component for dashboard stats.
 * Built on shadcn/ui Card primitive.
 */

import type { ReactNode } from "react";
import { Card, CardContent } from "@/components/ui/card";

interface StatCardProps {
  title: string;
  value: string | number;
  icon: ReactNode;
  variant?: "default" | "danger" | "warning" | "success";
  subtitle?: string;
}

export function StatCard({
  title,
  value,
  icon,
  variant = "default",
  subtitle,
}: StatCardProps) {
  const variantStyles = {
    default: "border-border",
    danger: "border-red-200 bg-red-50/50",
    warning: "border-amber-200 bg-amber-50/50",
    success: "border-emerald-200 bg-emerald-50/50",
  };

  const iconColors = {
    default: "text-muted-foreground",
    danger: "text-red-600",
    warning: "text-amber-600",
    success: "text-emerald-600",
  };

  return (
    <Card className={`${variantStyles[variant]} shadow-sm`}>
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{title}</p>
            <p className="mt-1 text-2xl font-bold tracking-tight">{value}</p>
            {subtitle && (
              <p className="mt-1 text-xs text-muted-foreground">{subtitle}</p>
            )}
          </div>
          <div className={`text-2xl ${iconColors[variant]}`}>{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}
