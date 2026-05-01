import { cn } from "@/lib/utils";
import { DOMAIN_COLOR_VAR, DOMAIN_LABELS, LEVEL_LABELS, LOCATION_LABELS, TYPE_ICONS, TYPE_LABELS } from "@/lib/enums";
import type { Domain, Level, LocationType, OpportunityType } from "@/lib/types";

interface BadgeBaseProps {
  className?: string;
  size?: "sm" | "md";
}

function basePill(size: "sm" | "md") {
  return cn(
    "inline-flex items-center gap-1.5 rounded-full border font-medium",
    size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
  );
}

export function DomainBadge({ domain, size = "sm", className }: BadgeBaseProps & { domain: Domain }) {
  const cssVar = DOMAIN_COLOR_VAR[domain];
  return (
    <span
      className={cn(basePill(size), className)}
      style={{
        color: `var(${cssVar})`,
        backgroundColor: `color-mix(in oklab, var(${cssVar}) 14%, transparent)`,
        borderColor: `color-mix(in oklab, var(${cssVar}) 30%, transparent)`,
      }}
    >
      <span
        className="h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: `var(${cssVar})` }}
      />
      {DOMAIN_LABELS[domain]}
    </span>
  );
}

export function TypeBadge({ type, size = "sm", className }: BadgeBaseProps & { type: OpportunityType }) {
  const Icon = TYPE_ICONS[type];
  return (
    <span
      className={cn(
        basePill(size),
        "border-border/60 bg-surface-elevated/60 text-foreground/85",
        className,
      )}
    >
      <Icon className="h-3 w-3" />
      {TYPE_LABELS[type]}
    </span>
  );
}

export function LevelBadge({ level, size = "sm", className }: BadgeBaseProps & { level: Level }) {
  return (
    <span className={cn(basePill(size), "border-border/60 bg-muted/60 text-muted-foreground", className)}>
      {LEVEL_LABELS[level]}
    </span>
  );
}

export function LocationBadge({ location, size = "sm", className }: BadgeBaseProps & { location: LocationType }) {
  return (
    <span className={cn(basePill(size), "border-border/60 bg-muted/40 text-muted-foreground", className)}>
      {LOCATION_LABELS[location]}
    </span>
  );
}

export function TagPill({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={cn(basePill("sm"), "border-border/40 bg-background/60 text-muted-foreground font-mono text-[10px] tracking-wide uppercase", className)}>
      {children}
    </span>
  );
}
