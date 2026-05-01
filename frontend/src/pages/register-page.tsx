import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowLeft, ArrowRight, Telescope, X } from "lucide-react";
import { api } from "@/lib/api";
import { authStore } from "@/lib/auth-store";
import { ALL_LEVELS, LEVEL_LABELS } from "@/lib/enums";
import type { Level } from "@/lib/types";

export function RegisterPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    email: "",
    full_name: "",
    password: "",
    academic_level: "master" as Level,
    institution: "",
    field_of_study: "",
    interests: [] as string[],
    skills: [] as string[],
    location_pref: "hybrid" as "remote" | "onsite" | "hybrid",
  });

  const update = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setLoading(true);
    const user = await api.register({
      email: form.email,
      full_name: form.full_name,
      academic_level: form.academic_level,
      institution: form.institution,
      field_of_study: form.field_of_study,
      interests: form.interests,
      skills: form.skills,
      preferences: { location: form.location_pref },
    });
    authStore.setAuth(user);
    navigate({ to: "/dashboard" });
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <div className="w-full max-w-lg">
        <Link to="/login" className="inline-flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground mb-6">
          <ArrowLeft className="h-3 w-3" /> Back to sign in
        </Link>

        <div className="rounded-2xl border border-border bg-card card-elevated p-6 md:p-8">
          <div className="flex items-center gap-2.5 mb-6">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-primary-glow shadow-glow">
              <Telescope className="h-4 w-4 text-primary-foreground" />
            </div>
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-primary">Step {step} of 3</div>
              <h2 className="font-display text-lg font-semibold">Create your account</h2>
            </div>
          </div>

          {/* Step indicator */}
          <div className="flex gap-1.5 mb-7">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={`h-1 flex-1 rounded-full ${s <= step ? "bg-primary" : "bg-muted"} transition-colors`}
              />
            ))}
          </div>

          {step === 1 && (
            <div className="space-y-4">
              <Field label="Email">
                <input type="email" required value={form.email} onChange={(e) => update("email", e.target.value)}
                  className="w-full rounded-lg bg-input border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-primary" />
              </Field>
              <Field label="Full name">
                <input type="text" required value={form.full_name} onChange={(e) => update("full_name", e.target.value)}
                  className="w-full rounded-lg bg-input border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-primary" />
              </Field>
              <Field label="Password">
                <input type="password" required value={form.password} onChange={(e) => update("password", e.target.value)}
                  className="w-full rounded-lg bg-input border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-primary" />
              </Field>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <Field label="Academic level">
                <select value={form.academic_level} onChange={(e) => update("academic_level", e.target.value as Level)}
                  className="w-full rounded-lg bg-input border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-primary">
                  {ALL_LEVELS.filter((l) => l !== "all").map((l) => (
                    <option key={l} value={l}>{LEVEL_LABELS[l]}</option>
                  ))}
                </select>
              </Field>
              <Field label="Institution">
                <input type="text" value={form.institution} onChange={(e) => update("institution", e.target.value)}
                  placeholder="e.g. ETH Zürich"
                  className="w-full rounded-lg bg-input border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-primary" />
              </Field>
              <Field label="Field of study">
                <input type="text" value={form.field_of_study} onChange={(e) => update("field_of_study", e.target.value)}
                  placeholder="e.g. Artificial Intelligence"
                  className="w-full rounded-lg bg-input border border-border px-3 py-2.5 text-sm focus:outline-none focus:border-primary" />
              </Field>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <TagInput label="Interests" placeholder="e.g. computer vision" values={form.interests} onChange={(v) => update("interests", v)} />
              <TagInput label="Skills" placeholder="e.g. PyTorch" values={form.skills} onChange={(v) => update("skills", v)} />
              <Field label="Location preference">
                <div className="grid grid-cols-3 gap-2">
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
            </div>
          )}

          <div className="mt-7 flex gap-3">
            {step > 1 && (
              <button onClick={() => setStep(step - 1)}
                className="px-4 py-2.5 rounded-lg border border-border text-sm hover:bg-surface-elevated transition-colors">
                Back
              </button>
            )}
            {step < 3 ? (
              <button onClick={() => setStep(step + 1)}
                className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-glow px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow">
                Continue <ArrowRight className="h-4 w-4" />
              </button>
            ) : (
              <button disabled={loading} onClick={submit}
                className="flex-1 inline-flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-primary to-primary-glow px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-glow disabled:opacity-60">
                {loading ? "Creating…" : "Create account"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
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
    <Field label={label}>
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
          className="flex-1 rounded-lg bg-input border border-border px-3 py-2 text-sm focus:outline-none focus:border-primary"
        />
        <button type="button" onClick={add}
          className="px-3 py-2 rounded-lg border border-border text-xs hover:bg-surface-elevated">Add</button>
      </div>
    </Field>
  );
}
