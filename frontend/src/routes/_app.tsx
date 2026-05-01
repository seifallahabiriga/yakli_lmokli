import { createFileRoute, Outlet, redirect } from "@tanstack/react-router";
import { AppLayout } from "@/components/layout/app-layout";
import { authStore } from "@/lib/auth-store";

export const Route = createFileRoute("/_app")({
  beforeLoad: () => {
    if (!authStore.get().user) {
      throw redirect({ to: "/login" });
    }
  },
  component: () => (
    <AppLayout>
      <Outlet />
    </AppLayout>
  ),
});
