import type { Metadata } from "next";
import { AnalyticsDashboard } from "@/components/analytics/AnalyticsDashboard";

export const metadata: Metadata = {
  title: "System analytics · RAG at Scale",
};

export default function AnalyticsPage() {
  return <AnalyticsDashboard />;
}
