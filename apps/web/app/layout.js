import "./globals.css";
import { AppShell } from "../components/app-shell";

export const metadata = {
  title: "Atlas",
  description: "Infrastructure knowledge and documentation",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
