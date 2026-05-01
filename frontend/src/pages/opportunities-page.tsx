import { useEffect, useMemo, useState } from "react";
import { Search, SlidersHorizontal, X } from "lucide-react";
import { api, type OpportunityFilters } from "@/lib/api";
import { ALL_DOMAINS, ALL_LEVELS, ALL_LOCATIONS, ALL_TYPES, DOMAIN_LABELS, LEVEL_LABELS, LOCATION_LABELS, TYPE_LABELS } from "@/lib/enums";
import { PageHeader, EmptyState, LoadingDots } from "@/components/ui/primitives";
import { OpportunityCard } from "@/components/opportunities/opportunity-card";
import type { OpportunitySummary } from "@/lib/types";

export function OpportunitiesPage() {
  const [filters, setFilters] = useState<OpportunityFilters>({ page: 1, page_size: 12, sort: "newest" });
  const [items, setItems] = useState<OpportunitySummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    setLoading(true);
    api.listOpportunities(filters).then((res) => {
      setItems(res.items); setTotal(res.total); setLoading(false);
    });
  }, [filters]);

  const update = (p: Partial<OpportunityFilters>) => setFilters((f) => ({ ...f, ...p, page: 1 }));
  const clear = () => setFilters({ page: 1, page_size: 12, sort: "newest" });

  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (filters.type) n++;
    if (filters.domain) n++;
    if (filters.level) n++;
    if (filters.location_type) n++;
    if (filters.is_paid != null) n++;
    if (filters.search) n++;
    return n;
  }, [filters]);

  return (
    <div>
      <PageHeader
        eyebrow="Catalogue"
        title="Opportunities"
        description="Every active opportunity scraped, classified, and ready to filter."
      />

      {/* Search bar */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[260px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search title, organization, or tag…"
            value={filters.search ?? ""}
            onChange={(e) => update({ search: e.target.value || undefined })}
            className="w-full rounded-lg bg-input border border-border pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:border-primary"
          />
        </div>
        <select
          value={filters.sort}
          onChange={(e) => update({ sort: e.target.value as OpportunityFilters["sort"] })}
          className="rounded-lg bg-input border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-primary"
        >
          <option value="newest">Newest</option>
          <option value="deadline">Deadline soonest</option>
          <option value="relevance">Most relevant</option>
        </select>
        <button
          onClick={() => setFiltersOpen((v) => !v)}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-input px-3 py-2.5 text-sm hover:bg-surface-elevated transition-colors lg:hidden"
        >
          <SlidersHorizontal className="h-4 w-4" />
          Filters {activeFilterCount > 0 && <span className="text-primary">({activeFilterCount})</span>}
        </button>
      </div>

      <div className="grid lg:grid-cols-12 gap-6">
        {/* Filter sidebar */}
        <aside className={`lg:col-span-3 ${filtersOpen ? "" : "hidden lg:block"}`}>
          <div className="rounded-xl border border-border bg-card card-elevated p-5 space-y-5 sticky top-20">
            <div className="flex items-center justify-between">
              <h3 className="font-display text-sm font-semibold uppercase tracking-wide">Filters</h3>
              {activeFilterCount > 0 && (
                <button onClick={clear} className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1">
                  Clear <X className="h-3 w-3" />
                </button>
              )}
            </div>

            <FilterGroup label="Type" options={ALL_TYPES.map((t) => [t, TYPE_LABELS[t]])} value={filters.type} onChange={(v) => update({ type: v })} />
            <FilterGroup label="Domain" options={ALL_DOMAINS.map((d) => [d, DOMAIN_LABELS[d]])} value={filters.domain} onChange={(v) => update({ domain: v })} />
            <FilterGroup label="Level" options={ALL_LEVELS.map((l) => [l, LEVEL_LABELS[l]])} value={filters.level} onChange={(v) => update({ level: v })} />
            <FilterGroup label="Location" options={ALL_LOCATIONS.map((l) => [l, LOCATION_LABELS[l]])} value={filters.location_type} onChange={(v) => update({ location_type: v })} />

            <div>
              <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">Compensation</div>
              <div className="flex gap-2">
                {[
                  { label: "Any", val: undefined },
                  { label: "Paid", val: true },
                  { label: "Unpaid", val: false },
                ].map((o) => (
                  <button
                    key={String(o.val)}
                    onClick={() => update({ is_paid: o.val })}
                    className={`flex-1 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
                      filters.is_paid === o.val
                        ? "border-primary bg-primary/15 text-primary"
                        : "border-border bg-input text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </aside>

        {/* Results */}
        <div className="lg:col-span-9">
          <div className="flex items-center justify-between mb-4">
            <div className="font-mono text-xs text-muted-foreground tracking-wide">
              {loading ? "Loading…" : <><span className="text-foreground font-semibold">{total}</span> result{total === 1 ? "" : "s"}</>}
            </div>
          </div>

          {loading ? (
            <div className="py-20 flex justify-center"><LoadingDots /></div>
          ) : items.length === 0 ? (
            <EmptyState title="No matches" description="Try adjusting your filters or search term." />
          ) : (
            <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {items.map((op) => (
                <OpportunityCard key={op.id} opportunity={op} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FilterGroup({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: Array<[string, string]>;
  value: string | undefined;
  onChange: (v: string | undefined) => void;
}) {
  return (
    <div>
      <div className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-2">{label}</div>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || undefined)}
        className="w-full rounded-lg bg-input border border-border px-3 py-2 text-sm focus:outline-none focus:border-primary"
      >
        <option value="">Any</option>
        {options.map(([v, l]) => (
          <option key={v} value={v}>{l}</option>
        ))}
      </select>
    </div>
  );
}
