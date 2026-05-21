"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const MODES = [
  { id: "chat", href: "/", label: "Chat" },
  { id: "infra", href: "/infra", label: "EC2 Infra" }
] as const;

export function ViewModeSwitch() {
  const pathname = usePathname();
  const active = pathname?.startsWith("/infra") ? "infra" : "chat";

  return (
    <nav className="viewModeSwitch" aria-label="Visualization mode">
      {MODES.map((mode) => (
        <Link
          key={mode.id}
          href={mode.href}
          className={`viewModeSwitchBtn ${active === mode.id ? "viewModeSwitchBtnActive" : ""}`}
          aria-current={active === mode.id ? "page" : undefined}
        >
          {mode.label}
        </Link>
      ))}
    </nav>
  );
}
