import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IDE Platform",
  description: "Team web IDE for MCP + OpenAI"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="container">{children}</div>
      </body>
    </html>
  );
}
