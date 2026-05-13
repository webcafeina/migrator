"use client";

import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";

export function LogoutButton() {
  const router = useRouter();

  async function handleLogout() {
    try {
      await api.post("/api/v1/auth/logout");
    } catch {
      // Aunque falle, hacer logout local
    }
    router.push("/login");
    router.refresh();
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={handleLogout}
      title="Cerrar sesión"
      className="h-8 w-8"
    >
      <LogOut className="h-4 w-4" />
    </Button>
  );
}
