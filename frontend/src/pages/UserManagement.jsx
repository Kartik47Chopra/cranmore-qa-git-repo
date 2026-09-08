import React, { useEffect, useState } from "react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { UserPlus, ShieldCheck, ShieldOff, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";

export default function UserManagement() {
  const { user, companies } = useAuth();
  const [users, setUsers] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "trade", company_id: "" });
  const [saving, setSaving] = useState(false);

  const load = () => api.get("/users").then(({ data }) => setUsers(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const compName = (id) => companies.find((c) => c.id === id)?.name || "—";

  const create = async () => {
    if (!form.email || !form.password) { toast.error("Email and password required"); return; }
    setSaving(true);
    try {
      await api.post("/users", form);
      toast.success("Account created");
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "trade", company_id: "" });
      load();
    } catch (e) {
      toast.error(formatApiErrorDetail(e.response?.data?.detail) || "Failed to create");
    } finally { setSaving(false); }
  };

  const setRole = async (u, role) => {
    await api.patch(`/users/${u.id}`, { role });
    toast.success(`${u.email} is now ${role}`);
    load();
  };

  const remove = async (u) => {
    if (!window.confirm(`Delete ${u.email}?`)) return;
    try { await api.delete(`/users/${u.id}`); toast.success("Deleted"); load(); }
    catch (e) { toast.error(formatApiErrorDetail(e.response?.data?.detail)); }
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <header className="px-6 py-4 border-b border-slate-200 bg-white shrink-0 flex items-center justify-between">
        <div>
          <h1 className="font-display text-2xl font-bold uppercase tracking-tight text-slate-900">User Management</h1>
          <p className="text-sm text-muted-foreground">Create logins for your team &amp; subcontractors, and grant admin rights</p>
        </div>
        <Button onClick={() => setOpen(true)} data-testid="add-user-btn" className="bg-emerald-700 hover:bg-emerald-800 text-white"><UserPlus size={16} className="mr-2" /> New Account</Button>
      </header>

      <div className="flex-1 overflow-y-auto">
        <Table>
          <TableHeader className="sticky top-0 bg-slate-50 z-10">
            <TableRow>
              <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Company</TableHead>
              <TableHead>Role</TableHead><TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {users.map((u) => (
              <TableRow key={u.id} data-testid={`user-row-${u.id}`}>
                <TableCell className="font-medium">{u.name}</TableCell>
                <TableCell className="text-sm">{u.email}</TableCell>
                <TableCell className="text-sm text-slate-500">{compName(u.company_id)}</TableCell>
                <TableCell>
                  <span className={`text-xs font-semibold rounded-full px-2 py-0.5 ${u.role === "admin" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{u.role}</span>
                </TableCell>
                <TableCell className="text-right space-x-1">
                  {u.role === "admin" ? (
                    <Button size="sm" variant="ghost" onClick={() => setRole(u, "trade")} data-testid={`revoke-admin-${u.id}`}><ShieldOff size={14} className="mr-1" /> Revoke admin</Button>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => setRole(u, "admin")} data-testid={`grant-admin-${u.id}`}><ShieldCheck size={14} className="mr-1 text-emerald-600" /> Make admin</Button>
                  )}
                  {u.id !== user?.id && (
                    <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => remove(u)} data-testid={`delete-user-${u.id}`}><Trash2 size={14} className="text-red-500" /></Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent data-testid="create-user-modal">
          <DialogHeader><DialogTitle className="font-display uppercase">New Account</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label>Full name</Label><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="user-name" /></div>
            <div className="space-y-1.5"><Label>Email</Label><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} data-testid="user-email" /></div>
            <div className="space-y-1.5"><Label>Password</Label><Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} data-testid="user-password" /></div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="user-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="admin">Admin (full access)</SelectItem>
                    <SelectItem value="pm">Project Manager</SelectItem>
                    <SelectItem value="trade">Trade / Subcontractor</SelectItem>
                    <SelectItem value="viewer">Viewer</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Company</Label>
                <Select value={form.company_id} onValueChange={(v) => setForm({ ...form, company_id: v })}>
                  <SelectTrigger data-testid="user-company"><SelectValue placeholder="Company" /></SelectTrigger>
                  <SelectContent>
                    {companies.map((c) => <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={create} disabled={saving} className="bg-emerald-700 hover:bg-emerald-800 text-white" data-testid="user-submit">
              {saving && <Loader2 size={15} className="mr-1.5 animate-spin" />} Create Account
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
