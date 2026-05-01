import { Link } from "@tanstack/react-router";
import { ArrowUpRight, Building2, Globe2 } from "lucide-react";
import { DeadlinePill } from "@/components/ui/deadline-pill";
import { DomainBadge, LevelBadge, LocationBadge, TagPill, TypeBadge } from "@/components/ui/badges";
import type { OpportunitySummary } from "@/lib/types";

export function OpportunityCard({
  opportunity,
  compact = false,
}: {
  opportunity: OpportunitySummary;
  compact?: boolean;
}) {
  const op = opportunity;
  return (
    <Link
      to="/opportunities/$id"
      params={{ id: String(op.id) }}
      className="group block rounded-xl border border-border bg-card p-5 card-elevated transition-all hover:border-primary/50 hover:-translate-y-0.5 hover:shadow-glow"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <TypeBadge type={op.type} />
          <DomainBadge domain={op.domain} />
        </div>
        <DeadlinePill deadline={op.deadline} />
      </div>

      <h3 className="font-display text-base font-semibold mt-3 leading-snug group-hover:text-primary transition-colors">
        {op.title}
      </h3>

      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        {op.organization && (
          <span className="inline-flex items-center gap-1.5">
            <Building2 className="h-3 w-3" /> {op.organization}
          </span>
        )}
        {op.country && (
          <span className="inline-flex items-center gap-1.5">
            <Globe2 className="h-3 w-3" /> {op.country}
          </span>
        )}
      </div>

      {!compact && op.tags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {op.tags.slice(0, 3).map((t) => (
            <TagPill key={t}>{t}</TagPill>
          ))}
          {op.tags.length > 3 && <TagPill>+{op.tags.length - 3}</TagPill>}
        </div>
      )}

      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <LevelBadge level={op.level} />
          <LocationBadge location={op.location_type} />
          {op.is_paid && (
            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border border-success/30 bg-success/10 text-success">
              Paid
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 text-xs text-muted-foreground group-hover:text-primary transition-colors">
          View <ArrowUpRight className="h-3.5 w-3.5" />
        </div>
      </div>
    </Link>
  );
}
