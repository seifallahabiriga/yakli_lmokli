import { useEffect, useState } from "react";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis, Cell } from "recharts";
import { api } from "@/lib/api";
import { PageHeader, Panel, LoadingDots } from "@/components/ui/primitives";
import { DOMAIN_COLOR_VAR, DOMAIN_LABELS } from "@/lib/enums";
import type { ClusterSummary } from "@/lib/types";

export function ClustersPage() {
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listClusters().then((c) => { setClusters(c); setLoading(false); });
  }, []);

  const data = clusters.map((c, i) => ({
    x: i + 1,
    y: c.member_count,
    z: c.member_count * 12,
    name: c.name,
    keywords: c.top_keywords.slice(0, 3).join(", "),
    color: `var(${DOMAIN_COLOR_VAR[c.dominant_domains[0]]})`,
  }));

  return (
    <div>
      <PageHeader
        eyebrow="Topic map"
        title="Semantic clusters"
        description="Opportunities are embedded and grouped by topic similarity. Each bubble is one cluster; size shows how many opportunities live there."
      />

      <Panel title="Cluster bubble map" className="mb-6">
        <div className="h-80">
          {loading ? (
            <div className="h-full flex items-center justify-center"><LoadingDots /></div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" />
                <XAxis type="number" dataKey="x" name="Cluster" stroke="var(--muted-foreground)" fontSize={11}
                  domain={[0, clusters.length + 1]} tickCount={clusters.length + 2} />
                <YAxis type="number" dataKey="y" name="Members" stroke="var(--muted-foreground)" fontSize={11} />
                <ZAxis type="number" dataKey="z" range={[200, 1500]} />
                <Tooltip
                  cursor={{ strokeDasharray: "3 3", stroke: "var(--primary)" }}
                  contentStyle={{ background: "var(--popover)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
                  formatter={(_v: unknown, _n: unknown, p: { payload?: { keywords?: string } }) => p.payload?.keywords ?? ""}
                  labelFormatter={(_l: unknown, payload: ReadonlyArray<{ payload?: { name?: string } }>) =>
                    payload?.[0]?.payload?.name ?? ""}
                />
                <Scatter data={data}>
                  {data.map((d, i) => <Cell key={i} fill={d.color} fillOpacity={0.7} stroke={d.color} />)}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          )}
        </div>
      </Panel>

      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {clusters.map((c) => {
          const cssVar = DOMAIN_COLOR_VAR[c.dominant_domains[0]];
          return (
            <div key={c.id} className="rounded-xl border border-border bg-card card-elevated p-5 hover:border-primary/40 hover:-translate-y-0.5 transition">
              <div className="flex items-start justify-between mb-3">
                <div
                  className="h-10 w-10 rounded-xl flex items-center justify-center font-mono text-sm font-bold shrink-0"
                  style={{
                    background: `color-mix(in oklab, var(${cssVar}) 18%, transparent)`,
                    color: `var(${cssVar})`,
                    border: `1px solid color-mix(in oklab, var(${cssVar}) 35%, transparent)`,
                    boxShadow: `0 0 16px -4px var(${cssVar})`,
                  }}
                >
                  {c.member_count}
                </div>
                <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">#{c.id}</span>
              </div>
              <h3 className="font-display text-base font-semibold leading-snug">{c.name}</h3>
              <div className="mt-3 flex flex-wrap gap-1">
                {c.top_keywords.slice(0, 5).map((k) => (
                  <span key={k} className="px-2 py-0.5 text-[10px] rounded-md bg-muted text-muted-foreground border border-border font-mono">
                    {k}
                  </span>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap gap-1">
                {c.dominant_domains.map((d) => {
                  const v = DOMAIN_COLOR_VAR[d];
                  return (
                    <span
                      key={d}
                      className="px-2 py-0.5 text-[10px] rounded-full border font-medium"
                      style={{
                        color: `var(${v})`,
                        background: `color-mix(in oklab, var(${v}) 14%, transparent)`,
                        borderColor: `color-mix(in oklab, var(${v}) 30%, transparent)`,
                      }}
                    >
                      {DOMAIN_LABELS[d]}
                    </span>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
