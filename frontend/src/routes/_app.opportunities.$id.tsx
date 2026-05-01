import { createFileRoute } from "@tanstack/react-router";
import { OpportunityDetailPage } from "@/pages/opportunity-detail-page";

export const Route = createFileRoute("/_app/opportunities/$id")({
  component: OpportunityDetailPage,
});
