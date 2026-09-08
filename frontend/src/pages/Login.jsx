import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Clover, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { formatApiErrorDetail } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("factory@maxxdoors.com.au");
  const [password, setPassword] = useState("Cranmore2026!");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/dashboard");
    } catch (err) {
      setError(formatApiErrorDetail(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-screen flex">
      <div className="hidden lg:flex flex-col justify-between w-1/2 bg-[#0F172A] p-12 relative overflow-hidden">
        <div
          className="absolute inset-0 opacity-25 bg-cover bg-center"
          style={{ backgroundImage: "url('https://images.pexels.com/photos/8961146/pexels-photo-8961146.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940')" }}
        />
        <div className="absolute inset-0 bg-gradient-to-t from-[#0F172A] via-[#0F172A]/70 to-transparent" />
        <div className="relative flex items-center gap-3">
          <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-400 to-emerald-700 flex items-center justify-center shadow-lg">
            <Clover size={26} className="text-white" />
          </div>
          <div>
            <div className="font-display font-bold text-3xl tracking-wide text-white leading-none">Cranmore</div>
            <div className="text-xs uppercase tracking-[0.3em] text-emerald-400">Carpenters QA</div>
          </div>
        </div>
        <div className="relative">
          <h1 className="font-display text-5xl font-bold text-white leading-tight uppercase">Build quality<br />you can prove.</h1>
          <p className="text-slate-300 mt-4 max-w-md">Track inspections, checklists and hold points across every location, template and trade — with photo evidence, geotags and live rollups.</p>
        </div>
      </div>

      <div className="flex-1 flex items-center justify-center p-8 bg-background">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" data-testid="login-form">
          <div>
            <h2 className="font-display text-3xl font-bold uppercase tracking-tight">Sign in</h2>
            <p className="text-sm text-muted-foreground mt-1">Access your project quality workspace.</p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" data-testid="login-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" data-testid="login-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          {error && <div data-testid="login-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">{error}</div>}
          <Button type="submit" data-testid="login-submit" disabled={loading} className="w-full bg-emerald-600 hover:bg-emerald-700 text-white">
            {loading && <Loader2 size={16} className="mr-2 animate-spin" />} Sign in
          </Button>
          <p className="text-xs text-muted-foreground text-center">Demo admin prefilled — click Sign in to explore.</p>
        </form>
      </div>
    </div>
  );
}
