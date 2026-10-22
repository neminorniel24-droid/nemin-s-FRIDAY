import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false, // strict mode would start the microphone/camera twice in dev
};

export default nextConfig;
