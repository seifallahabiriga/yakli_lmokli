import { createFileRoute } from "@tanstack/react-router";
import { OpportunitiesPage } from "@/pages/opportunities-page";

export const Route = createFileRoute("/_app/opportunities")({
  component: OpportunitiesPage,
});
