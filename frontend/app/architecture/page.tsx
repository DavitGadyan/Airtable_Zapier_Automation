import { ArchitectureExplorer } from "@/components/architecture/architecture-explorer";

export const metadata = {
  title: "Architecture · Construction Ops Automation",
};

/**
 * The Architecture tab.
 *
 * Renders entirely from static data in lib/architecture-data.ts. No fetch, no
 * backend dependency -- this page is shown to people who make buying
 * decisions, and a demo that fails because a service is cold is a demo that
 * failed for no reason.
 */
export default function ArchitecturePage() {
  return (
    <div className="h-[calc(100vh-3.25rem)]">
      <ArchitectureExplorer />
    </div>
  );
}
