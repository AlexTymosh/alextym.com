import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = dirname(fileURLToPath(import.meta.url));

/** @type {import("next").NextConfig} */
const nextConfig = {
  turbopack: {
    root: appRoot,
  },
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
