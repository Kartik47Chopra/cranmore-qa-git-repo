import React, { useEffect, useState } from "react";
import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, ListChecks, Grid3x3, Settings, Milestone, FileSpreadsheet, ChevronDown, LogOut, Clover, Building, FileText, FileBarChart2, UserCog } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useProject } from "@/context/ProjectContext";
import { LocationTree } from "@/components/LocationTree";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger, DropdownMenuLabel, DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testid: "nav-dashboard" },
  { to: "/your-list", label: "Your List", icon: ListChecks, testid: "nav-your-list" },
  { to: "/tracker", label: "Multi-Template Tracker", icon: Grid3x3, testid: "nav-tracker" },
  { to: "/documents", label: "Documents", icon: FileText, testid: "nav-documents" },
  { to: "/milestones", label: "Milestone Tracker", icon: Milestone, testid: "nav-milestones" },
  { to: "/report", label: "Progress Report", icon: FileBarChart2, testid: "nav-report" },
  { to: "/setup", label: "Project Setup", icon: Settings, testid: "nav-setup" },
  { to: "/users", label: "User Management", icon: UserCog, testid: "nav-users", adminOnly: true },
];

export default function Layout() {
  const { user, logout, companies } = useAuth();
  const { projects, project, projectId, setProjectId } = useProject();
  const [locations, setLocations] = useState([]);
  const navigate = useNavigate();
  const company = companies.find((c) => c.id === user?.company_id);

  useEffect(() => {
    if (projectId) api.get(`/projects/${projectId}/locations`).then(({ data }) => setLocations(data));
  }, [projectId]);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background">
      {/* Sidebar */}
      <aside className="w-[264px] shrink-0 bg-[#0F172A] text-slate-200 flex flex-col border-r border-slate-800">
        <div className="px-4 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="h-9 w-9 rounded-lg bg-gradient-to-br from-emerald-400 to-emerald-700 flex items-center justify-center shadow-inner">
              <Clover size={20} className="text-white" />
            </div>
            <div>
              <div className="font-display font-bold text-xl leading-none tracking-wide text-white">Cranmore</div>
              <div className="text-[10px] uppercase tracking-[0.28em] text-emerald-400">Carpenters QA</div>
            </div>
          </div>
        </div>

        {/* Company + Project switchers */}
        <div className="px-3 py-3 border-b border-slate-800 space-y-2">
          <div className="flex items-center gap-2 text-xs text-slate-400 px-1" data-testid="company-switcher-trigger">
            <Building size={13} className="text-emerald-400" />
            <span className="truncate">{company?.name || "Cranmore Carpenters"}</span>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="project-switcher" className="w-full flex items-center justify-between gap-2 rounded-md bg-slate-800 hover:bg-slate-700 px-3 py-2 text-sm font-semibold transition-colors">
                <span className="truncate">{project?.name || "Select project"}</span>
                <ChevronDown size={15} className="text-slate-400" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56">
              <DropdownMenuLabel>Projects</DropdownMenuLabel>
              {projects.map((p) => (
                <DropdownMenuItem key={p.id} data-testid={`project-option-${p.id}`} onClick={() => setProjectId(p.id)}>
                  {p.name}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Nav */}
        <nav className="px-2 py-2 space-y-0.5">
          {navItems.filter((n) => !n.adminOnly || user?.role === "admin").map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              data-testid={n.testid}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  isActive ? "bg-emerald-500 text-slate-900" : "text-slate-300 hover:bg-slate-800"
                }`
              }
            >
              <n.icon size={16} />
              {n.label}
            </NavLink>
          ))}
        </nav>

        {/* Location tree */}
        <div className="flex-1 overflow-y-auto sidebar-scroll px-2 pb-4 mt-1">
          <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider text-slate-500">Locations</div>
          <LocationTree locations={locations} />
        </div>

        {/* User */}
        <div className="border-t border-slate-800 p-3">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button data-testid="user-menu-trigger" className="w-full flex items-center gap-2 rounded-md hover:bg-slate-800 px-2 py-1.5 transition-colors">
                <div className="h-7 w-7 rounded-full bg-emerald-500 text-slate-900 flex items-center justify-center text-xs font-bold">
                  {user?.name?.[0] || "U"}
                </div>
                <div className="text-left flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{user?.name}</div>
                  <div className="text-[10px] text-slate-400 uppercase">{user?.role}</div>
                </div>
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-56" align="start">
              <DropdownMenuLabel className="truncate">{user?.email}</DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem data-testid="logout-btn" onClick={async () => { await logout(); navigate("/login"); }}>
                <LogOut size={14} className="mr-2" /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-hidden flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
