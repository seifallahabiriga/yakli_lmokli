import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { Telescope, Mail, Lock, Sparkles, ArrowRight } from "lucide-react";
import { authStore } from "@/lib/auth-store";
import { api } from "@/lib/api";

export function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("alex.chen@university.edu");
  const [password, setPassword] = useState("demo");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const user = await api.login(email, password);
    authStore.setAuth(user);
    navigate({ to: "/dashboard" });
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left: brand panel */}
      <div className="hidden lg:flex relative overflow-hidden flex-col justify-between p-10 border-r border-border bg-sidebar">
        <div className="absolute inset-0 opacity-40 pointer-events-none"
             style={{
               backgroundImage:
                 "radial-gradient(circle at 30% 30%, color-mix(in oklab, var(--primary) 30%, transparent), transparent 50%), radial-gradient(circle at 70% 70%, color-mix(in oklab, var(--accent) 25%, transparent), transparent 55%)",
             }} />
        <div className="relative">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-glow shadow-glow">
              <Telescope className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <div className="font-display text-base font-semibold">University</div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">Observatory</div>
            </div>
          </div>
        </div>
        <div className="relative max-w-md">
          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary mb-3">
            For AI & Data Science researchers
          </div>
          <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight">
            Discover internships, scholarships, research projects — scored for you.
          </h1>
          <p className="mt-4 text-muted-foreground">
            We continuously scrape and cluster opportunities, then rank them by your
            skills, domain, deadline, and location preferences.
          </p>
          <div className="mt-8 grid grid-cols-3 gap-4">
            {[
              { k: "Opportunities", v: "1.2k+" },
              { k: "Clusters", v: "47" },
              { k: "Updated", v: "Daily" },
            ].map((s) => (
              <div key={s.k}>
                <div className="font-display text-2xl font-semibold">{s.v}</div>
                <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">{s.k}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="relative font-mono text-[11px] text-muted-foreground">
          v1.0 · academic edition
        </div>
      </div>

      {/* Right: form */}
      <div className="flex items-center justify-center p-6 md:p-10">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2.5 mb-8">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-primary-glow shadow-glow">
              <Telescope className="h-5 w-5 text-primary-foreground" />
            </div>
            <div className="font-display text-lg font-semibold">Observatory</div>
          </div>

          <div className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary mb-2">Sign in</div>
          <h2 className="font-display text-2xl font-semibold mb-1">Welcome back</h2>
          <p className="text-sm text-muted-foreground mb-8">Sign in to view your personalized recommendations.</p>

          <form onSubmit={submit} className="space-y-4">
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground">Email</span>
              <div className="mt-1 relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg bg-input border border-border pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </label>
            <label className="block">
              <span className="text-xs font-medium text-muted-foreground">Password</span>
              <div className="mt-1 relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-lg bg-input border border-border pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </label>

            <button
              disabled={loading}
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-glow px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow hover:opacity-95 transition disabled:opacity-60"
            >
              {loading ? "Signing in…" : (<>Sign in <ArrowRight className="h-4 w-4" /></>)}
            </button>

            <div className="rounded-lg border border-border bg-muted/40 p-3 text-[11px] text-muted-foreground flex items-start gap-2">
              <Sparkles className="h-3.5 w-3.5 text-primary mt-0.5 shrink-0" />
              <span>Demo mode — any credentials work. Pre-filled with the demo account.</span>
            </div>

            <div className="text-center text-xs text-muted-foreground">
              No account?{" "}
              <Link to="/register" className="text-primary hover:underline">Create one</Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
