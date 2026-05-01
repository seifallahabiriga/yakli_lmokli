// Stub pages — implementations land in next batch.
export const placeholder = (label: string) => () => (
  <div className="text-muted-foreground">Loading {label}…</div>
);

export const LoginPage = placeholder("login");
export const RegisterPage = placeholder("register");
export const DashboardPage = placeholder("dashboard");
export const OpportunitiesPage = placeholder("opportunities");
export const OpportunityDetailPage = placeholder("opportunity");
export const RecommendationsPage = placeholder("recommendations");
export const ClustersPage = placeholder("clusters");
export const NotificationsPage = placeholder("notifications");
export const ProfilePage = placeholder("profile");
