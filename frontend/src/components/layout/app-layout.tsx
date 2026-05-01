import { Outlet } from "@tanstack/react-router";
import { MobileNav, MobileTopbar, Sidebar, Topbar } from "./sidebar";

export function AppLayout({ children }: { children?: React.ReactNode }) {
  return (
    <div className="min-h-screen flex">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <MobileTopbar />
        <Topbar />
        <main className="flex-1 px-4 md:px-8 py-6 md:py-8 pb-20 md:pb-8">
          {children ?? <Outlet />}
        </main>
      </div>
      <MobileNav />
    </div>
  );
}

