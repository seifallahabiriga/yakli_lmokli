import { createFileRoute } from "@tanstack/react-router";
import { ClustersPage } from "@/pages/clusters-page";

export const Route = createFileRoute("/_app/clusters")({
  component: ClustersPage,
});
