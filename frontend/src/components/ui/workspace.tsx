import type { ReactNode } from "react";

/** Accessible page frame; its landmark is the shared skip-link target. */
export function Workspace({
  children,
}: Readonly<{ children: ReactNode }>): React.JSX.Element {
  return (
    <main id="main-content" tabIndex={-1} className="workspace">
      {children}
    </main>
  );
}
