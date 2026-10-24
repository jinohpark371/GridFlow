import type { Metadata, Viewport } from "next";
import { IBM_Plex_Sans_KR } from "next/font/google";
import "./globals.css";

// 숫자 폭이 일정한 고딕 하나로 통일 — "3 / 20"·순서 번호가 흔들리지 않게. 빌드 때 파일로 받아 함께 배포된다
const plexSansKr = IBM_Plex_Sans_KR({
  weight: ["400", "500", "600"],
  subsets: ["latin"],
  display: "swap",
  variable: "--font-plex",
});

export const metadata: Metadata = {
  title: "GridFlow",
  description: "테마에 어울리는 사진을 골라 캐러셀 순서를 추천해요",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f2f2" },
    { media: "(prefers-color-scheme: dark)", color: "#161616" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" className={plexSansKr.variable}>
      <body>{children}</body>
    </html>
  );
}
