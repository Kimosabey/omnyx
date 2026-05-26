import { create } from "zustand";
import type { AuthUser } from "@/lib/keycloak";

interface AuthState {
  user:            AuthUser | null;
  isAuthenticated: boolean;
  isLoading:       boolean;
  setUser:    (user: AuthUser | null) => void;
  setLoading: (v: boolean)           => void;
  clear:      ()                     => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user:            null,
  isAuthenticated: false,
  isLoading:       true,

  setUser: (user) => set({ user, isAuthenticated: !!user }),
  setLoading: (isLoading) => set({ isLoading }),
  clear: () => set({ user: null, isAuthenticated: false }),
}));
