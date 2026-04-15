import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { useState } from "react"
import { Toaster } from "@/components/ui/sonner"

export function AppProviders({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 4_000,
            refetchInterval: 8_000,
            retry: 1,
          },
        },
      }),
  )

  return (
    <QueryClientProvider client={client}>
      {children}
      <Toaster richColors position="bottom-right" />
    </QueryClientProvider>
  )
}
