import { useEffect, useState } from "react";
import { Bell, BookOpen, CheckCheck, Clock, Network, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { PageHeader, EmptyState, LoadingDots } from "@/components/ui/primitives";
import type { NotificationSummary, NotificationType } from "@/lib/types";

const ICONS: Record<NotificationType, React.ReactNode> = {
  new_opportunity: <Sparkles className="h-4 w-4" />,
  deadline_reminder: <Clock className="h-4 w-4" />,
  new_recommendation: <Bell className="h-4 w-4" />,
  cluster_update: <Network className="h-4 w-4" />,
  system: <BookOpen className="h-4 w-4" />,
};

const TYPE_TONE: Record<NotificationType, string> = {
  new_opportunity: "var(--primary)",
  deadline_reminder: "var(--warning)",
  new_recommendation: "var(--accent)",
  cluster_update: "var(--chart-4)",
  system: "var(--muted-foreground)",
};

const TABS = [
  { id: "all", label: "All" },
  { id: "unread", label: "Unread" },
  { id: "deadline_reminder", label: "Deadlines" },
  { id: "new_opportunity", label: "New" },
] as const;

export function NotificationsPage() {
  const [items, setItems] = useState<NotificationSummary[]>([]);
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("all");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const res = await api.myNotifications();
    setItems(res.items);
    setLoading(false);
  };
  useEffect(() => { load(); }, []);

  const filtered = items.filter((n) => {
    if (tab === "all") return true;
    if (tab === "unread") return n.status === "unread";
    return n.type === tab;
  });

  const click = async (n: NotificationSummary) => {
    if (n.status === "unread") {
      await api.markNotificationRead(n.id);
      load();
    }
  };

  const markAll = async () => {
    await api.markAllRead();
    load();
  };

  const formatTime = (iso: string) => {
    const diff = Date.now() - new Date(iso).getTime();
    const min = Math.floor(diff / 60000);
    if (min < 60) return `${Math.max(1, min)}m ago`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
  };

  return (
    <div>
      <PageHeader eyebrow="Inbox" title="Notifications" description="Updates from the pipeline: new matches, deadline alerts, cluster shifts.">
        <button
          onClick={markAll}
          className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-surface-elevated transition-colors"
        >
          <CheckCheck className="h-4 w-4" /> Mark all read
        </button>
      </PageHeader>

      <div className="inline-flex rounded-lg border border-border bg-card p-1 mb-4">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              tab === t.id ? "bg-primary text-primary-foreground shadow-glow" : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 flex justify-center"><LoadingDots /></div>
      ) : filtered.length === 0 ? (
        <EmptyState title="Nothing here" description="No notifications match this filter." />
      ) : (
        <ul className="rounded-xl border border-border bg-card card-elevated overflow-hidden divide-y divide-border">
          {filtered.map((n) => (
            <li
              key={n.id}
              onClick={() => click(n)}
              className={`flex items-start gap-4 p-4 cursor-pointer transition-colors ${
                n.status === "unread" ? "bg-primary/5 hover:bg-primary/10" : "hover:bg-surface-elevated"
              }`}
            >
              <div
                className="h-9 w-9 rounded-lg flex items-center justify-center shrink-0"
                style={{
                  color: TYPE_TONE[n.type],
                  background: `color-mix(in oklab, ${TYPE_TONE[n.type]} 14%, transparent)`,
                  border: `1px solid color-mix(in oklab, ${TYPE_TONE[n.type]} 30%, transparent)`,
                }}
              >
                {ICONS[n.type]}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  {n.status === "unread" && <span className="h-1.5 w-1.5 rounded-full bg-primary shadow-glow" />}
                  <div className="text-sm font-medium leading-snug">{n.title}</div>
                </div>
                <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground mt-1">
                  {n.type.replace(/_/g, " ")} · {formatTime(n.created_at)}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
