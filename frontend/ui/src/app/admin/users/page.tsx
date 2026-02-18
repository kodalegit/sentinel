"use client";

/**
 * User Management page — admin only.
 */

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getUsers,
  createUser,
  updateUser,
  type ApiUser,
} from "@/lib/api";
import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/lib/auth";
import { useRouter } from "next/navigation";
import {
  Users,
  Plus,
  Pencil,
  UserX,
  UserCheck,
  Shield,
  X,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const ROLE_CONFIG: Record<string, { label: string; color: string }> = {
  admin: { label: "Admin", color: "text-[#c4412f] bg-[#c4412f]/10 border-[#c4412f]/20" },
  supervisor: { label: "Supervisor", color: "text-[#b78b43] bg-[#b78b43]/10 border-[#b78b43]/20" },
  auditor: { label: "Auditor", color: "text-[#1f6f5c] bg-[#1f6f5c]/10 border-[#1f6f5c]/20" },
};

function UserManagementContent() {
  const { isAdmin, user: currentUser } = useAuth();
  const router = useRouter();
  const queryClient = useQueryClient();

  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<ApiUser | null>(null);

  // Redirect non-admins
  if (!isAdmin) {
    router.replace("/");
    return null;
  }

  const { data: users = [], isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: getUsers,
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateUser(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  return (
    <div className="min-h-screen pb-12">
      <header className="border-b border-border/70 bg-card/70 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-5xl mx-auto px-6 lg:px-10">
          <div className="flex items-end justify-between py-6">
            <div>
              <p className="text-[11px] uppercase tracking-[0.35em] text-muted-foreground">
                Administration
              </p>
              <h1 className="font-display text-3xl text-foreground">User Management</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Create and manage system users and their roles.
              </p>
            </div>
            <Button
              onClick={() => setCreateOpen(true)}
              className="flex items-center gap-2"
            >
              <Plus size={16} />
              New User
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 lg:px-10 py-8">
        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground">
            Loading users…
          </div>
        ) : (
          <div className="rounded-2xl border border-border/60 bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/60 bg-muted/30">
                  <th className="text-left px-5 py-3 text-[11px] uppercase tracking-wider text-muted-foreground font-medium">User</th>
                  <th className="text-left px-5 py-3 text-[11px] uppercase tracking-wider text-muted-foreground font-medium">Role</th>
                  <th className="text-left px-5 py-3 text-[11px] uppercase tracking-wider text-muted-foreground font-medium">Status</th>
                  <th className="text-left px-5 py-3 text-[11px] uppercase tracking-wider text-muted-foreground font-medium">Created</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const roleCfg = ROLE_CONFIG[u.role];
                  const isSelf = u.id === currentUser?.id;
                  return (
                    <tr
                      key={u.id}
                      className="border-b border-border/40 last:border-0 hover:bg-muted/20 transition-colors"
                    >
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-semibold uppercase">
                            {u.full_name.charAt(0)}
                          </span>
                          <div>
                            <p className="font-medium text-foreground/90">
                              {u.full_name}
                              {isSelf && (
                                <span className="ml-2 text-[10px] text-muted-foreground">(you)</span>
                              )}
                            </p>
                            <p className="text-xs text-muted-foreground">{u.username} · {u.email}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        {roleCfg ? (
                          <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded border ${roleCfg.color}`}>
                            <Shield size={10} />
                            {roleCfg.label}
                          </span>
                        ) : (
                          <span className="text-muted-foreground">{u.role}</span>
                        )}
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded border ${
                          u.is_active
                            ? "text-[#1f6f5c] bg-[#1f6f5c]/10 border-[#1f6f5c]/20"
                            : "text-muted-foreground bg-muted/50 border-border/50"
                        }`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${u.is_active ? "bg-[#1f6f5c]" : "bg-muted-foreground"}`} />
                          {u.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-muted-foreground">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setEditUser(u)}
                            className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                            title="Edit user"
                          >
                            <Pencil size={14} />
                          </button>
                          {!isSelf && (
                            <button
                              onClick={() => toggleActive.mutate({ id: u.id, is_active: !u.is_active })}
                              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                              title={u.is_active ? "Deactivate user" : "Activate user"}
                            >
                              {u.is_active ? <UserX size={14} /> : <UserCheck size={14} />}
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <CreateUserDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={() => {
          queryClient.invalidateQueries({ queryKey: ["users"] });
          setCreateOpen(false);
        }}
      />

      {editUser && (
        <EditUserDialog
          user={editUser}
          onClose={() => setEditUser(null)}
          onUpdated={() => {
            queryClient.invalidateQueries({ queryKey: ["users"] });
            setEditUser(null);
          }}
        />
      )}
    </div>
  );
}

function CreateUserDialog({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    username: "",
    email: "",
    full_name: "",
    password: "",
    role: "auditor",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      await createUser(form);
      setForm({ username: "", email: "", full_name: "", password: "", role: "auditor" });
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-md bg-card border border-border/70">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Users size={18} />
            Create New User
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          <Field label="Full Name">
            <input
              type="text"
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              required
              className="input-field"
              placeholder="Jane Doe"
            />
          </Field>
          <Field label="Username">
            <input
              type="text"
              value={form.username}
              onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
              required
              className="input-field"
              placeholder="jane.doe"
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required
              className="input-field"
              placeholder="jane@example.com"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              required
              minLength={8}
              className="input-field"
              placeholder="Min. 8 characters"
            />
          </Field>
          <Field label="Role">
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              className="input-field"
            >
              <option value="auditor">Auditor</option>
              <option value="supervisor">Supervisor</option>
              <option value="admin">Admin</option>
            </select>
          </Field>

          {error && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create User"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditUserDialog({
  user,
  onClose,
  onUpdated,
}: {
  user: ApiUser;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [form, setForm] = useState({
    full_name: user.full_name,
    email: user.email,
    role: user.role,
    password: "",
  });
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const payload: Record<string, string> = {
        full_name: form.full_name,
        email: form.email,
        role: form.role,
      };
      if (form.password) payload.password = form.password;
      await updateUser(user.id, payload);
      onUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update user");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-md bg-card border border-border/70">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil size={18} />
            Edit User — {user.username}
          </DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          <Field label="Full Name">
            <input
              type="text"
              value={form.full_name}
              onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
              required
              className="input-field"
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              value={form.email}
              onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
              required
              className="input-field"
            />
          </Field>
          <Field label="Role">
            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              className="input-field"
            >
              <option value="auditor">Auditor</option>
              <option value="supervisor">Supervisor</option>
              <option value="admin">Admin</option>
            </select>
          </Field>
          <Field label="New Password (leave blank to keep current)">
            <input
              type="password"
              value={form.password}
              onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              className="input-field"
              placeholder="Leave blank to keep current"
            />
          </Field>

          {error && (
            <div className="flex items-center gap-2 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
              <AlertCircle size={14} />
              {error}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="outline" onClick={onClose} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving…" : "Save Changes"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-foreground">{label}</label>
      {children}
    </div>
  );
}

export default function UserManagementPage() {
  return (
    <AuthGuard>
      <UserManagementContent />
    </AuthGuard>
  );
}
