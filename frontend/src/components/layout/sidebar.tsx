import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import {
  Bell,
  Compass,
  LayoutDashboard,
  LogOut,
  Network,
  Sparkles,
  Telescope,
  User,
} from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/opportunities", label: "Opportunities", icon: Compass },
  { to: "/recommendations", label: "Recommendations", icon: Sparkles },
  { to: "/clusters", label: "Clusters", icon: Network },
  { to: "/notifications", label: "Notifications", icon: Bell },
  { to: "/profile", label: "Profile", icon: User },
] as const;

export function Sidebar() {
  const location = useLocation();
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <aside className="hidden md:flex w-60 lg:w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex items-center gap-2.5 px-5 h-16 border-b border-sidebar-border">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary-glow shadow-glow">
          <Telescope className="h-5 w-5 text-primary-foreground" />
        </div>
        <div>
          <div className="font-display text-sm font-semibold tracking-tight">University</div>
          <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            Observatory
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto scrollbar-thin px-3 py-4 space-y-0.5">
        {NAV.map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to || location.pathname.startsWith(to + "/");
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground border border-primary/20"
                  : "text-sidebar-foreground/70 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
              )}
            >
              <Icon className={cn("h-4 w-4", active && "text-primary")} />
              <span>{label}</span>
              {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary shadow-glow" />}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
          <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-xs font-semibold text-primary-foreground">
            {user?.full_name.split(" ").map((p) => p[0]).join("").slice(0, 2)}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">{user?.full_name}</div>
            <div className="text-[11px] text-muted-foreground truncate">{user?.institution}</div>
          </div>
          <button
            onClick={() => {
              logout();
              navigate({ to: "/login" });
            }}
            className="text-muted-foreground hover:text-foreground p-1 rounded transition-colors"
            aria-label="Log out"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}

export function MobileTopbar() {
  const { user } = useAuth();
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    let alive = true;
    const tick = () => api.unreadNotifications().then((r) => alive && setUnread(r.length));
    tick();
    const id = setInterval(tick, 60_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <header className="md:hidden flex items-center justify-between px-4 h-14 border-b border-border bg-sidebar">
      <Link to="/dashboard" className="flex items-center gap-2">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary-glow">
          <Telescope className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="font-display font-semibold">Observatory</span>
      </Link>
      <Link to="/notifications" className="relative">
        <Bell className="h-5 w-5 text-muted-foreground" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 h-4 w-4 rounded-full bg-destructive text-[10px] font-bold flex items-center justify-center text-destructive-foreground">
            {unread}
          </span>
        )}
        <span className="sr-only">{user?.full_name}</span>
      </Link>
    </header>
  );
}

export function MobileNav() {
  const location = useLocation();
  return (
    <nav className="md:hidden fixed bottom-0 inset-x-0 z-30 border-t border-border bg-sidebar/95 backdrop-blur">
      <div className="grid grid-cols-5">
        {NAV.slice(0, 5).map(({ to, label, icon: Icon }) => {
          const active = location.pathname === to || location.pathname.startsWith(to + "/");
          return (
            <Link
              key={to}
              to={to}
              className={cn(
                "flex flex-col items-center gap-0.5 py-2 text-[10px]",
                active ? "text-primary" : "text-muted-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}

export function Topbar({ children }: { children?: React.ReactNode }) {
  const [unread, setUnread] = useState(0);
  useEffect(() => {
    let alive = true;
    const tick = () => api.unreadNotifications().then((r) => alive && setUnread(r.length));
    tick();
    const id = setInterval(tick, 60_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <header className="hidden md:flex items-center justify-between h-16 px-6 border-b border-border bg-background/60 backdrop-blur sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-full border border-success/30 bg-success/10 px-3 py-1">
          <span className="h-1.5 w-1.5 rounded-full bg-success animate-pulse" />
          <span className="text-[11px] font-mono uppercase tracking-wider text-success">Live</span>
        </div>
        {children}
      </div>
      <Link to="/notifications" className="relative p-2 rounded-lg hover:bg-surface-elevated transition-colors">
        <Bell className="h-5 w-5 text-muted-foreground" />
        {unread > 0 && (
          <span className="absolute top-1 right-1 h-4 w-4 rounded-full bg-destructive text-[10px] font-bold flex items-center justify-center text-destructive-foreground">
            {unread}
          </span>
        )}
      </Link>
    </header>
  );
}
