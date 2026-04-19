import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import {
  fetchMe,
  postLogin,
  postLogout,
  postRegister,
  type AuthUser,
  type RegisterInput,
} from "@/api/fetch"

type AuthStatus = "loading" | "anon" | "authed"

type AuthContextValue = {
  status: AuthStatus
  user: AuthUser | null
  isAdmin: boolean
  login: (username: string, password: string) => Promise<void>
  register: (input: RegisterInput) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [status, setStatus] = useState<AuthStatus>("loading")

  const refresh = useCallback(async () => {
    try {
      const res = await fetchMe()
      if (res.authenticated && res.user) {
        setUser(res.user)
        setStatus("authed")
        return
      }
    } catch {
      // fall through to anon
    }
    setUser(null)
    setStatus("anon")
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const login = useCallback(async (username: string, password: string) => {
    const u = await postLogin(username, password)
    setUser(u)
    setStatus("authed")
  }, [])

  const register = useCallback(async (input: RegisterInput) => {
    const u = await postRegister(input)
    setUser(u)
    setStatus("authed")
  }, [])

  const logout = useCallback(async () => {
    await postLogout()
    setUser(null)
    setStatus("anon")
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      isAdmin: Boolean(user?.is_admin),
      login,
      register,
      logout,
      refresh,
    }),
    [status, user, login, register, logout, refresh],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = (): AuthContextValue => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error("useAuth must be used within AuthProvider")
  return ctx
}
