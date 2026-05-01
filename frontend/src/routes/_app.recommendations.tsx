import { createFileRoute } from "@tanstack/react-router";
import { RecommendationsPage } from "@/pages/recommendations-page";

export const Route = createFileRoute("/_app/recommendations")({
  component: RecommendationsPage,
});
