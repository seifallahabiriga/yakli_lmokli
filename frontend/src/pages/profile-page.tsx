import { useState } from "react";
import { X, Save, Check } from "lucide-react";
import { useAuth } from "@/lib/auth-store";
import { api } from "@/lib/api";
import { authStore } from "@/lib/auth-store";
import { PageHeader, Panel } from "@/components/ui/primitives";
import { ALL_LEVELS, LEVEL_LABELS } from "@/lib/enums";
import type { Level } from "@/lib/types";

export function ProfilePage() {
  const { user } = useAuth();
  const [form, setForm] = useState(() => ({
    full_name: user?.full_name ?? "",
    bio: user?.bio ?? "",
    institution: user?.institution ?? "",
    field_of_study: user?.field_of_study ?? "",
    academic_level: (user?.academic_level ?? "master") as Level,
    skills: user?.skills ?? [],
    interests: user?.interests ?? [],
    location_pref: ((user?.preferences as Record<string, unknown>)?.location ?? "hybrid") as "remote" | "onsite" | "hybrid",
  }));
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  if (!user) return null;

  const update = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    setSaving(true);
    const updated = await api.updateMe({
      full_name: form.full_name,
      bio: form.bio,
      institution: form.institution,
      field_of_study: form.field_of_study,
      academic_level: form.academic_level,
      skills: form.skills,
      interests: form.interests,
      preferences: { ...user.preferences, location: form.location_pref },
    });
    authStore.setAuth(updated);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div>
      <PageHeader eyebrow="Account" title="Profile" description="Your profile drives the recommendation engine — better signal in, better matches out." />

      <div className="grid lg:grid-cols-12 gap-6">
        <div className="lg:col-span-4">
          <Panel>
            <div className="flex flex-col items-center text-center">
              <div className="h-20 w-20 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-2xl font-display font-semibold text-primary-foreground shadow-glow">
                {form.full_name.split(" ").map((p) => p[0]).join("").slice(0, 2)}
              </div>
              <div className="mt-3 font-display text-lg font-semibold">{form.full_name}</div>
              <div className="text-xs text-muted-foreground">{user.email}</div>
              <div className="mt-3 flex gap-1.5">
                <span className="px-2 py-0.5 text-[11px] rounded-full border border-primary/30 bg-primary/10 text-primary capitalize">{user.role}</span>
                {user.is_verified && (
                  <span className="px-2 py-0.5 text-[11px] rounded-full border border-success/30 bg-success/10 text-success inline-flex items-center gap-1">
                    <Check className="h-3 w-3" /> Verified
                  </span>
                )}
              </div>
            </div>
            <dl className="mt-5 pt-5 border-t border-border space-y-2 text-xs">
              <Row k="Member since" v={new Date(user.created_at).toLocaleDateString()} />
              <Row k="Last login" v={user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : "—"} />
              <Row k="ID" v={`#${user.id}`} mono />
            </dl>
          </Panel>
        </div>

        <div className="lg:col-span-8 space-y-6">
          <Panel title="Identity">
            <div className="grid sm:grid-cols-2 gap-4">
              <Field label="Full name">
                <input type="text" value={form.full_name} onChange={(e) => update("full_name", e.target.value)} className="input" />
              </Field>
              <Field label="Academic level">
                <select value={form.academic_level} onChange={(e) => update("academic_level", e.target.value as Level)} className="input">
                  {ALL_LEVELS.filter((l) => l !== "all").map((l) => <option key={l} value={l}>{LEVEL_LABELS[l]}</option>)}
                </select>
              </Field>
              <Field label="Institution">
                <input type="text" value={form.institution} onChange={(e) => update("institution", e.target.value)} className="input" />
              </Field>
              <Field label="Field of study">
                <input type="text" value={form.field_of_study} onChange={(e) => update("field_of_study", e.target.value)} className="input" />
              </Field>
            </div>
            <Field label="Bio" className="mt-4">
              <textarea rows={3} value={form.bio} onChange={(e) => update("bio", e.target.value)} className="input" />
            </Field>
          </Panel>

          <Panel title="Skills & interests">
            <TagInput label="Skills" values={form.skills} onChange={(v) => update("skills", v)} placeholder="e.g. PyTorch" />
            <div className="h-4" />
            <TagInput label="Interests" values={form.interests} onChange={(v) => update("interests", v)} placeholder="e.g. computer vision" />
          </Panel>

          <Panel title="Preferences">
            <Field label="Location preference">
              <div className="grid grid-cols-3 gap-2 max-w-md">
                {(["remote", "hybrid", "onsite"] as const).map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => update("location_pref", opt)}
                    className={`px-3 py-2 rounded-lg text-xs font-medium border transition-colors capitalize ${
                      form.location_pref === opt
                        ? "border-primary bg-primary/15 text-primary"
                        : "border-border bg-input text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </Field>
          </Panel>

          <div className="flex items-center gap-3">
            <button
              disabled={saving}
              onClick={save}
              className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-glow px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow hover:opacity-95 disabled:opacity-60 transition"
            >
              <Save className="h-4 w-4" />
              {saving ? "Saving…" : "Save changes"}
            </button>
            {saved && (
              <span className="inline-flex items-center gap-1.5 text-xs text-success">
                <Check className="h-3.5 w-3.5" /> Saved — recommendations will recompute.
              </span>
            )}
          </div>
        </div>
      </div>

      <style>{`
        .input {
          width: 100%;
          background: var(--input);
          border: 1px solid var(--border);
          border-radius: 0.5rem;
          padding: 0.625rem 0.75rem;
          font-size: 0.875rem;
          color: var(--foreground);
          outline: none;
        }
        .input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px color-mix(in oklab, var(--primary) 20%, transparent); }
      `}</style>
    </div>
  );
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className={mono ? "font-mono text-foreground/80" : "text-foreground/80"}>{v}</dd>
    </div>
  );
}

function TagInput({
  label,
  placeholder,
  values,
  onChange,
}: {
  label: string;
  placeholder?: string;
  values: string[];
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const v = draft.trim();
    if (!v || values.includes(v)) return;
    onChange([...values, v]);
    setDraft("");
  };
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground mb-2">{label}</div>
      <div className="flex flex-wrap gap-1.5 mb-2">
        {values.map((v) => (
          <span key={v} className="inline-flex items-center gap-1 px-2 py-1 rounded-full bg-primary/15 text-primary text-xs border border-primary/30">
            {v}
            <button type="button" onClick={() => onChange(values.filter((x) => x !== v))} className="hover:text-foreground">
              <X className="h-3 w-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          type="text"
          value={draft}
          placeholder={placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }}
          className="input"
        />
        <button type="button" onClick={add} className="px-3 py-2 rounded-lg border border-border text-xs hover:bg-surface-elevated whitespace-nowrap">
          Add
        </button>
      </div>
    </div>
  );
}
