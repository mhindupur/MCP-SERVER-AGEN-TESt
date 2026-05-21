"use client";

export type DisplayMode = "view" | "diagram";

type Props = {
  mode: DisplayMode;
  onChange: (mode: DisplayMode) => void;
  className?: string;
};

export function DisplayModeSwitch({ mode, onChange, className }: Props) {
  return (
    <nav className={`viewModeSwitch ${className || ""}`} aria-label="Display mode">
      <button
        type="button"
        className={`viewModeSwitchBtn ${mode === "view" ? "viewModeSwitchBtnActive" : ""}`}
        onClick={() => onChange("view")}
        aria-current={mode === "view" ? "true" : undefined}
      >
        View
      </button>
      <button
        type="button"
        className={`viewModeSwitchBtn ${mode === "diagram" ? "viewModeSwitchBtnActive" : ""}`}
        onClick={() => onChange("diagram")}
        aria-current={mode === "diagram" ? "true" : undefined}
      >
        Diagram
      </button>
    </nav>
  );
}
