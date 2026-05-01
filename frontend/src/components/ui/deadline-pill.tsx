import { cn } from "@/lib/utils";
import { Calendar, Clock, Infinity as InfinityIcon } from "lucide-react";

interface DeadlinePillProps {
  deadline: string | null;
  className?: string;
}

export function DeadlinePill({ deadline, className }: DeadlinePillProps) {
  if (!deadline) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
          "border-primary/30 bg-primary/10 text-primary",
          className,
        )}
      >
        <InfinityIcon className="h-3 w-3" />
        Rolling
      </span>
    );
  }

  const date = new Date(deadline);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const days = Math.floor(diffMs / 86400000);

  if (diffMs < 0) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
          "border-border bg-muted/60 text-muted-foreground",
          className,
        )}
      >
        <Calendar className="h-3 w-3" />
        Expired
      </span>
    );
  }

  let tone: "ok" | "warn" | "danger" = "ok";
  if (days < 7) tone = "danger";
  else if (days < 30) tone = "warn";

  const styles =
    tone === "danger"
      ? { color: "var(--destructive)", bg: "color-mix(in oklab, var(--destructive) 14%, transparent)", border: "color-mix(in oklab, var(--destructive) 35%, transparent)" }
      : tone === "warn"
      ? { color: "var(--warning)", bg: "color-mix(in oklab, var(--warning) 14%, transparent)", border: "color-mix(in oklab, var(--warning) 35%, transparent)" }
      : { color: "var(--success)", bg: "color-mix(in oklab, var(--success) 14%, transparent)", border: "color-mix(in oklab, var(--success) 35%, transparent)" };

  const label =
    days === 0
      ? "Today!"
      : days < 7
      ? `${days} day${days === 1 ? "" : "s"} left`
      : days < 30
      ? `${days} days left`
      : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        tone === "danger" && "animate-pulse",
        className,
      )}
      style={{ color: styles.color, backgroundColor: styles.bg, borderColor: styles.border }}
    >
      <Clock className="h-3 w-3" />
      {label}
    </span>
  );
}
