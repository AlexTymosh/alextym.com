/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    if (!process.env.BACKEND_ORIGIN) {
      return [];
    }

    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_ORIGIN}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
