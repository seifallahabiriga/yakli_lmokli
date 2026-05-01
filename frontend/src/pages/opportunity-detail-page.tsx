import { Link, useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { ArrowLeft, Building2, ExternalLink, Globe2, Bookmark } from "lucide-react";
import { api } from "@/lib/api";
import { DeadlinePill } from "@/components/ui/deadline-pill";
import { DomainBadge, LevelBadge, LocationBadge, TagPill, TypeBadge } from "@/components/ui/badges";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { Panel, LoadingDots } from "@/components/ui/primitives";
import type { OpportunityPublic, OpportunitySummary } from "@/lib/types";

export function OpportunityDetailPage() {
  const { id } = useParams({ from: "/_app/opportunities/$id" });
  const [op, setOp] = useState<OpportunityPublic | null>(null);
  const [related, setRelated] = useState<OpportunitySummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getOpportunity(Number(id)).then(async (data) => {
      setOp(data);
      if (data?.cluster_id) {
        const r = await api.listOpportunities({ cluster_id: data.cluster_id, page_size: 4 });
        setRelated(r.items.filter((x) => x.id !== data.id).slice(0, 3));
      }
      setLoading(false);
    });
  }, [id]);

  if (loading) return <div className="py-20 flex justify-center"><LoadingDots /></div>;
  if (!op) return <div className="text-muted-foreground">Opportunity not found.</div>;

  return (
    <div>
      <Link to="/opportunities" className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground mb-6">
        <ArrowLeft className="h-3 w-3" /> All opportunities
      </Link>

      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-8 space-y-6">
          {/* Header card */}
          <div className="rounded-xl border border-border bg-card card-elevated p-6">
            <div className="flex flex-wrap items-center gap-1.5 mb-4">
              <TypeBadge type={op.type} />
              <DomainBadge domain={op.domain} />
              <LevelBadge level={op.level} />
              <LocationBadge location={op.location_type} />
              {op.is_paid && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border border-success/30 bg-success/10 text-success">Paid</span>
              )}
            </div>

            <h1 className="font-display text-2xl md:text-3xl font-semibold leading-tight">{op.title}</h1>

            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground">
              {op.organization && <span className="inline-flex items-center gap-1.5"><Building2 className="h-4 w-4" />{op.organization}</span>}
              {op.country && <span className="inline-flex items-center gap-1.5"><Globe2 className="h-4 w-4" />{op.country}</span>}
              <DeadlinePill deadline={op.deadline} />
            </div>

            <div className="mt-5 flex gap-3">
              <a
                href={op.url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-glow px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow hover:opacity-95 transition"
              >
                Apply on official site <ExternalLink className="h-4 w-4" />
              </a>
              <button className="inline-flex items-center gap-2 rounded-lg border border-border bg-input px-4 py-2.5 text-sm hover:bg-surface-elevated transition">
                <Bookmark className="h-4 w-4" /> Save
              </button>
            </div>
          </div>

          <Panel title="Description">
            <p className="text-sm text-foreground/90 leading-relaxed">{op.description}</p>
          </Panel>

          <Panel title="Required skills">
            <div className="flex flex-wrap gap-1.5">
              {op.required_skills.map((s) => (
                <span key={s} className="px-2.5 py-1 rounded-md bg-primary/10 text-primary border border-primary/30 text-xs font-medium">
                  {s}
                </span>
              ))}
            </div>
          </Panel>

          <Panel title="Tags">
            <div className="flex flex-wrap gap-1.5">
              {op.tags.map((t) => <TagPill key={t}>{t}</TagPill>)}
            </div>
          </Panel>
        </div>

        <div className="lg:col-span-4 space-y-6">
          <Panel title="Eligibility">
            <dl className="space-y-3">
              {Object.entries(op.eligibility).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 pb-2 border-b border-border last:border-0 last:pb-0">
                  <dt className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{k}</dt>
                  <dd className="text-sm text-foreground/90 text-right">{v}</dd>
                </div>
              ))}
            </dl>
          </Panel>

          <Panel title="Metadata">
            <dl className="space-y-2 text-xs">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">ID</dt>
                <dd className="font-mono text-foreground/80">#{op.id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Posted</dt>
                <dd>{new Date(op.posted_at).toLocaleDateString()}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Cluster</dt>
                <dd className="font-mono">#{op.cluster_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-muted-foreground">Status</dt>
                <dd className="capitalize text-success">{op.status}</dd>
              </div>
            </dl>
          </Panel>

          {related.length > 0 && (
            <div>
              <h3 className="font-display text-sm font-semibold uppercase tracking-wide mb-3">From the same cluster</h3>
              <div className="space-y-3">
                {related.map((r) => <OpportunityCard key={r.id} opportunity={r} compact />)}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
