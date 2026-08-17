import * as React from "react";

import { cn } from "@/lib/utils";

type Variant =
  | "default"
  | "accent"
  | "secondary"
  | "outline"
  | "ghost"
  | "success"
  | "warning"
  | "danger";

const VARIANTS: Record<Variant, string> = {
  default: "bg-surface-active text-primary border-transparent",
  accent: "bg-accent-subtle text-accent border-transparent",
  secondary: "bg-surface-active text-secondary border-transparent",
  outline: "bg-transparent text-secondary border-border",
  ghost: "bg-transparent text-tertiary border-transparent",
  success: "bg-success-subtle text-success border-transparent",
  warning: "bg-warning-subtle text-warning border-transparent",
  danger: "bg-danger-subtle text-danger border-transparent",
};

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
}

export function Badge({ className, variant = "default", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5",
        "text-[11px] font-medium leading-5",
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  );
}
