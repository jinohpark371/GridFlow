import type { NextConfig } from "next";

// 서버 기능 없이 정적 파일(out/)로 내보내 Netlify에 올린다 — 서버 역할은 FastAPI가 맡음
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
