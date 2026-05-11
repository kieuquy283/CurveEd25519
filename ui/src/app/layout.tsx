// import type { Metadata } from "next";
// import { Geist, Geist_Mono } from "next/font/google";
// import "./globals.css";
// import { WebSocketProvider } from "@/providers/WebSocketProvider";
// import { NotificationToaster } from "@/components/NotificationToaster";

// const geistSans = Geist({
//   variable: "--font-geist-sans",
//   subsets: ["latin"],
//   display: "swap",
// });

// const geistMono = Geist_Mono({
//   variable: "--font-geist-mono",
//   subsets: ["latin"],
//   display: "swap",
// });

// export const metadata: Metadata = {
//   title: "CurveApp — Secure Messenger",
//   description:
//     "Production-grade end-to-end encrypted messenger with Double Ratchet protocol",
//   keywords: ["secure messenger", "encrypted chat", "privacy"],
//   robots: "noindex",
// };

// export default function RootLayout({
//   children,
// }: Readonly<{ children: React.ReactNode }>) {
//   return (
//     <html
//       lang="en"
//       suppressHydrationWarning
//       className={`${geistSans.variable} ${geistMono.variable} dark h-full`}
//     >
//       <body className="h-full overflow-hidden bg-background text-foreground antialiased">
//         <WebSocketProvider>
//           {children}
//           <NotificationToaster />
//         </WebSocketProvider>
//       </body>
//     </html>
//   );
// }

import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Secure Messenger",
  description: "Secure Messenger UI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}