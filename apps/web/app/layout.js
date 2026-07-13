import "./globals.css";
import { RootShell } from "../components/root-shell";

export const metadata = {
  title: "Atlas",
  description: "Infrastructure knowledge and documentation",
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
