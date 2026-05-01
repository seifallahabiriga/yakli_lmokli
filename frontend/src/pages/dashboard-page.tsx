import { useEffect, useState } from "react";
import { Link } from "@tanstack/react-router";
import { Bell, Clock, RefreshCw, Sparkles, TrendingUp, Activity, AlertTriangle, ChevronRight } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth-store";
import { DOMAIN_COLOR_VAR, DOMAIN_LABELS, TYPE_LABELS } from "@/lib/enums";
import { PageHeader, Panel, StatCard, EmptyState, LoadingDots } from "@/components/ui/primitives";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import { RecommendationCard } from "@/components/recommendations/recommendation-card";
import { DeadlinePill } from "@/components/ui/deadline-pill";
import type { ClusterSummary, NotificationSummary, OpportunitySummary, RecommendationPublic } from "@/lib/types";

export function DashboardPage() {
  const { user } = useAuth();
  const [recs, setRecs] = useState<RecommendationPublic[]>([]);
  const [expiring, setExpiring] = useState<OpportunitySummary[]>([]);
  const [unread, setUnread] = useState<NotificationSummary[]>([]);
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [stats, setStats] = useState<{ by_type: Record<string, number>; by_domain: Record<string, number>; total: number } | null>(null);
  const [recomputing, setRecomputing] = useState(false);

  const loadAll = async () => {
    const [r, e, n, c, s] = await Promise.all([
      api.topRecommendations(5),
      api.expiringSoon(7),
      api.unreadNotifications(5),
      api.listClusters(),
      api.opportunityStats(),
    ]);
    setRecs(r); setExpiring(e); setUnread(n); setClusters(c); setStats(s);
  };

  useEffect(() => { loadAll(); }, []);

  const recompute = async () => {
    setRecomputing(true);
    await api.recomputeRecommendations();
    await new Promise((r) => setTimeout(r, 600));
    await loadAll();
    setRecomputing(false);
  };

  const profileCompleteness = (() => {
    if (!user) return 0;
    const fields = [user.bio, user.institution, user.field_of_study, user.academic_level];
    const arrays = [user.skills?.length, user.interests?.length];
    const filled = fields.filter(Boolean).length + arrays.filter((n) => (n ?? 0) > 0).length;
    return Math.round((filled / (fields.length + arrays.length)) * 100);
  })();

  const typeData = stats ? Object.entries(stats.by_type).map(([k, v]) => ({
    name: TYPE_LABELS[k as keyof typeof TYPE_LABELS] ?? k, value: v,
  })) : [];

  const domainData = stats ? Object.entries(stats.by_domain).map(([k, v]) => ({
    name: DOMAIN_LABELS[k as keyof typeof DOMAIN_LABELS] ?? k,
    value: v,
    color: `var(${DOMAIN_COLOR_VAR[k as keyof typeof DOMAIN_COLOR_VAR]})`,
  })) : [];

  return (
    <div>
      <PageHeader
        eyebrow={`Welcome back, ${user?.full_name.split(" ")[0] ?? ""}`}
        title="Mission control"
        description="Today's signal: new matches, deadlines closing, and what your clusters are telling us."
      >
        <button
          onClick={recompute}
          disabled={recomputing}
          className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-glow px-4 py-2 text-sm font-medium text-primary-foreground shadow-glow hover:opacity-95 disabled:opacity-60 transition"
        >
          <RefreshCw className={`h-4 w-4 ${recomputing ? "animate-spin" : ""}`} />
          {recomputing ? "Recomputing…" : "Refresh recommendations"}
        </button>
      </PageHeader>

      {/* stat row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-8">
        <StatCard label="Active opportunities" value={stats?.total ?? "—"} hint="across all domains" icon={<Activity className="h-4 w-4" />} />
        <StatCard label="Top recommendations" value={recs.length} hint={`avg ${Math.round((recs.reduce((s, r) => s + r.score, 0) / Math.max(recs.length, 1)) * 100)}% match`} icon={<Sparkles className="h-4 w-4" />} />
        <StatCard label="Expiring this week" value={expiring.length} hint="deadlines within 7 days" icon={<AlertTriangle className="h-4 w-4" />} />
        <StatCard label="Unread alerts" value={unread.length} hint="notifications waiting" icon={<Bell className="h-4 w-4" />} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Center column — feed */}
        <div className="lg:col-span-8 space-y-6">
          <Panel
            title="Top matches for you"
            action={
              <Link to="/recommendations" className="text-xs text-primary hover:underline inline-flex items-center gap-1">
                See all <ChevronRight className="h-3 w-3" />
              </Link>
            }
          >
            {recs.length === 0 ? (
              <LoadingDots />
            ) : (
              <div className="space-y-4">
                {recs.slice(0, 3).map((r) => (
                  <RecommendationCard key={r.id} rec={r} onChanged={loadAll} />
                ))}
              </div>
            )}
          </Panel>

          <div className="grid sm:grid-cols-2 gap-4">
            <Panel title="By type">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={typeData} margin={{ top: 4, right: 4, left: -20, bottom: 40 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="name" stroke="var(--muted-foreground)" fontSize={10} angle={-30} textAnchor="end" interval={0} />
                    <YAxis stroke="var(--muted-foreground)" fontSize={10} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="value" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
            <Panel title="By domain">
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={domainData} layout="vertical" margin={{ top: 4, right: 8, left: 8, bottom: 4 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" stroke="var(--muted-foreground)" fontSize={10} allowDecimals={false} />
                    <YAxis dataKey="name" type="category" stroke="var(--muted-foreground)" fontSize={10} width={90} />
                    <Tooltip contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                      {domainData.map((d, i) => <Cell key={i} fill={d.color} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Panel>
          </div>
        </div>

        {/* Right column — sidecar */}
        <div className="lg:col-span-4 space-y-6">
          <Panel title="Profile signal">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-muted-foreground">Completeness</span>
              <span className="font-mono text-sm tabular-nums text-primary">{profileCompleteness}%</span>
            </div>
            <div className="h-2 rounded-full bg-muted/60 overflow-hidden">
              <div
                className="h-full rounded-full bg-gradient-to-r from-primary to-accent transition-all duration-700"
                style={{ width: `${profileCompleteness}%`, boxShadow: "0 0 12px var(--primary)" }}
              />
            </div>
            <Link to="/profile" className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline">
              Update profile <ChevronRight className="h-3 w-3" />
            </Link>
          </Panel>

          <Panel
            title="Expiring soon"
            action={<TrendingUp className="h-4 w-4 text-warning" />}
          >
            {expiring.length === 0 ? (
              <EmptyState title="Nothing expiring" description="All clear for the next 7 days." />
            ) : (
              <ul className="space-y-3">
                {expiring.slice(0, 4).map((op) => (
                  <li key={op.id}>
                    <Link
                      to="/opportunities/$id"
                      params={{ id: String(op.id) }}
                      className="flex items-start gap-3 rounded-lg p-2 -mx-2 hover:bg-surface-elevated transition-colors"
                    >
                      <Clock className="h-4 w-4 text-warning mt-0.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">{op.title}</div>
                        <div className="text-xs text-muted-foreground truncate">{op.organization}</div>
                        <div className="mt-1"><DeadlinePill deadline={op.deadline} /></div>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel
            title="Unread alerts"
            action={
              <Link to="/notifications" className="text-xs text-primary hover:underline">View all</Link>
            }
          >
            {unread.length === 0 ? (
              <EmptyState title="Inbox zero" description="No unread notifications." />
            ) : (
              <ul className="space-y-2.5">
                {unread.map((n) => (
                  <li key={n.id} className="flex items-start gap-2.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary mt-2 shrink-0 shadow-glow" />
                    <div className="flex-1 min-w-0">
                      <div className="text-sm leading-snug">{n.title}</div>
                      <div className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">
                        {n.type.replace("_", " ")}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel
            title="Top clusters"
            action={
              <Link to="/clusters" className="text-xs text-primary hover:underline">Explore</Link>
            }
          >
            <ul className="space-y-3">
              {clusters.slice(0, 4).map((c) => {
                const cssVar = DOMAIN_COLOR_VAR[c.dominant_domains[0]];
                return (
                  <li key={c.id} className="flex items-start gap-3">
                    <div
                      className="h-8 w-8 rounded-lg flex items-center justify-center text-[10px] font-mono font-semibold shrink-0"
                      style={{
                        background: `color-mix(in oklab, var(${cssVar}) 18%, transparent)`,
                        color: `var(${cssVar})`,
                        border: `1px solid color-mix(in oklab, var(${cssVar}) 35%, transparent)`,
                      }}
                    >
                      {c.member_count}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium truncate">{c.name}</div>
                      <div className="text-[11px] text-muted-foreground truncate">
                        {c.top_keywords.slice(0, 3).join(" · ")}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          </Panel>
        </div>
      </div>
    </div>
  );
}
