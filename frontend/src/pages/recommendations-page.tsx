import { useEffect, useState } from "react";
import { Sliders } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader, EmptyState, LoadingDots } from "@/components/ui/primitives";
import { RecommendationCard } from "@/components/recommendations/recommendation-card";
import type { RecommendationPublic, RecommendationStatus } from "@/lib/types";

const TABS: Array<{ id: "all" | RecommendationStatus; label: string }> = [
  { id: "all", label: "All" },
  { id: "scored", label: "Scored" },
  { id: "applied", label: "Applied" },
  { id: "dismissed", label: "Dismissed" },
];

export function RecommendationsPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("all");
  const [minScore, setMinScore] = useState(0);
  const [items, setItems] = useState<RecommendationPublic[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const r = await api.myRecommendations({
      status: tab === "all" ? undefined : tab,
      min_score: minScore || undefined,
    });
    setItems(r);
    setLoading(false);
  };

  useEffect(() => { load(); }, [tab, minScore]);

  return (
    <div>
      <PageHeader
        eyebrow="Personalized"
        title="Your recommendations"
        description="Ranked by composite score across six signals: semantic similarity, skill overlap, domain, level, deadline, and location."
      />

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="inline-flex rounded-lg border border-border bg-card p-1">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                tab === t.id
                  ? "bg-primary text-primary-foreground shadow-glow"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 ml-auto">
          <div className="inline-flex items-center gap-2 text-xs text-muted-foreground">
            <Sliders className="h-3.5 w-3.5" />
            Min score:
            <span className="font-mono text-primary tabular-nums w-8">{Math.round(minScore * 100)}%</span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={minScore * 100}
            onChange={(e) => setMinScore(Number(e.target.value) / 100)}
            className="accent-primary"
          />
        </div>
      </div>

      {loading ? (
        <div className="py-20 flex justify-center"><LoadingDots /></div>
      ) : items.length === 0 ? (
        <EmptyState
          title="No recommendations yet"
          description="Update your profile with skills and interests to get better matches."
        />
      ) : (
        <div className="space-y-4">
          {items.map((r) => (
            <RecommendationCard key={r.id} rec={r} onChanged={load} />
          ))}
        </div>
      )}
    </div>
  );
}
