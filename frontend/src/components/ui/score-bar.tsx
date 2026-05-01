import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface ScoreBarProps {
  /** 0..1 */
  score: number;
  label?: string;
  showPercent?: boolean;
  size?: "sm" | "md" | "lg";
  className?: string;
}

function colorFor(score: number) {
  if (score >= 0.7) return "var(--success)";
  if (score >= 0.4) return "var(--warning)";
  return "var(--destructive)";
}

export function ScoreBar({ score, label, showPercent = true, size = "md", className }: ScoreBarProps) {
  const clamped = Math.max(0, Math.min(1, score));
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const id = requestAnimationFrame(() => setWidth(clamped * 100));
    return () => cancelAnimationFrame(id);
  }, [clamped]);

  const color = colorFor(clamped);
  const barH = size === "sm" ? "h-1.5" : size === "lg" ? "h-3" : "h-2";

  return (
    <div className={cn("w-full", className)}>
      {(label || showPercent) && (
        <div className="flex items-center justify-between mb-1.5">
          {label && <span className="text-xs text-muted-foreground">{label}</span>}
          {showPercent && (
            <span className="font-mono text-xs tabular-nums" style={{ color }}>
              {Math.round(clamped * 100)}%
            </span>
          )}
        </div>
      )}
      <div className={cn("w-full overflow-hidden rounded-full bg-muted/60", barH)}>
        <div
          className={cn("h-full rounded-full transition-[width] duration-700 ease-out")}
          style={{
            width: `${width}%`,
            background: `linear-gradient(90deg, color-mix(in oklab, ${color} 70%, transparent), ${color})`,
            boxShadow: `0 0 12px -2px ${color}`,
          }}
        />
      </div>
    </div>
  );
}
