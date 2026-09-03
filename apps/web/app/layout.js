import "./globals.css";
import { RootShell } from "../components/root-shell";

export const metadata = {
  title: "Atlas Impact",
  applicationName: "Atlas Impact",
  description: "Infrastructure knowledge and documentation",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Atlas Impact",
  },
  icons: {
    icon: [
      { url: "/branding/favicon.svg", type: "image/svg+xml" },
      { url: "/branding/favicon-32x32.png", sizes: "32x32", type: "image/png" },
      { url: "/branding/favicon-16x16.png", sizes: "16x16", type: "image/png" },
    ],
    shortcut: "/branding/favicon.ico",
    apple: [
      { url: "/branding/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
    ],
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <RootShell>{children}</RootShell>
      </body>
    </html>
  );
}
