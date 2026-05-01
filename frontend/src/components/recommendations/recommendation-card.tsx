import { useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import { ScoreBar } from "@/components/ui/score-bar";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { api } from "@/lib/api";
import type { RecommendationPublic, RecommendationStatus } from "@/lib/types";

const SIGNAL_LABELS: Record<keyof RecommendationPublic["score_breakdown"], string> = {
  semantic_similarity: "Semantic similarity",
  skill_overlap: "Skill overlap",
  domain_match: "Domain match",
  level_match: "Level match",
  deadline_proximity: "Deadline proximity",
  location_preference: "Location preference",
};

export function RecommendationCard({
  rec,
  onChanged,
}: {
  rec: RecommendationPublic;
  onChanged?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<RecommendationStatus>(rec.status);
  const [pending, setPending] = useState(false);

  const update = async (s: RecommendationStatus) => {
    setPending(true);
    setStatus(s);
    await api.setRecommendationStatus(rec.id, s);
    setPending(false);
    onChanged?.();
  };

  return (
    <div className="rounded-xl border border-border bg-card card-elevated overflow-hidden">
      <div className="p-5">
        <div className="flex items-start gap-4">
          <div className="flex-1 min-w-0">
            <OpportunityCard opportunity={rec.opportunity} compact />
          </div>
          <div className="hidden md:flex flex-col items-center gap-1 w-32 shrink-0">
            <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Match</div>
            <div className="font-display text-3xl font-semibold tabular-nums" style={{ color: rec.score >= 0.7 ? "var(--success)" : rec.score >= 0.4 ? "var(--warning)" : "var(--destructive)" }}>
              {Math.round(rec.score * 100)}%
            </div>
            <div className="font-mono text-[10px] text-muted-foreground">rank #{rec.rank}</div>
          </div>
        </div>

        <div className="mt-4">
          <ScoreBar score={rec.score} label="Composite score" />
        </div>

        {rec.explanation && (
          <p className="mt-3 italic text-sm text-muted-foreground border-l-2 border-primary/40 pl-3">
            {rec.explanation}
          </p>
        )}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <button
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:underline"
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
            Score breakdown
          </button>

          <div className="flex items-center gap-2">
            <StatusBadge status={status} />
            <button
              disabled={pending || status === "applied"}
              onClick={() => update("applied")}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-success/40 bg-success/10 text-success hover:bg-success/20 transition-colors disabled:opacity-50"
            >
              <Check className="h-3 w-3" /> Mark applied
            </button>
            <button
              disabled={pending || status === "dismissed"}
              onClick={() => update("dismissed")}
              className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium border border-border text-muted-foreground hover:text-foreground hover:bg-surface-elevated transition-colors disabled:opacity-50"
            >
              <X className="h-3 w-3" /> Dismiss
            </button>
          </div>
        </div>

        {open && (
          <div className="mt-4 pt-4 border-t border-border grid sm:grid-cols-2 gap-x-6 gap-y-3">
            {(Object.keys(SIGNAL_LABELS) as Array<keyof typeof SIGNAL_LABELS>).map((k) => (
              <ScoreBar key={k} score={rec.score_breakdown[k]} label={SIGNAL_LABELS[k]} size="sm" />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: RecommendationStatus }) {
  const map: Record<RecommendationStatus, { label: string; cls: string }> = {
    pending: { label: "Pending", cls: "border-border bg-muted text-muted-foreground" },
    scored: { label: "Scored", cls: "border-primary/30 bg-primary/10 text-primary" },
    applied: { label: "Applied", cls: "border-success/40 bg-success/10 text-success" },
    dismissed: { label: "Dismissed", cls: "border-border bg-muted/40 text-muted-foreground" },
  };
  const m = map[status];
  return <span className={`inline-flex items-center px-2 py-0.5 rounded-full border text-[11px] font-medium ${m.cls}`}>{m.label}</span>;
}
