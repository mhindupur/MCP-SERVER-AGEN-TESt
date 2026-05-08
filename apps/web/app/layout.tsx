import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IDE Platform",
  description: "Team web IDE for MCP + OpenAI"
};

const themeInitScript = `(function(){try{var t=localStorage.getItem("ide-theme");if(t==="dark"||t==="light"){document.documentElement.setAttribute("data-theme",t);}else{document.documentElement.setAttribute("data-theme","light");}}catch(e){document.documentElement.setAttribute("data-theme","light");}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <div className="container">{children}</div>
      </body>
    </html>
  );
}
