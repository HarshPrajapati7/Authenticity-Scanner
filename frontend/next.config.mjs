const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://127.0.0.1:8010";

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    root: process.cwd(),
  },
  async rewrites() {
    return [
      {
        source: "/api/documents/:path*",
        destination: `${backendUrl}/api/documents/:path*`,
      },
    ];
  },
};

export default nextConfig;
