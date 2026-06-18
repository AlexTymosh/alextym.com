import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const appRoot = dirname(fileURLToPath(import.meta.url));

/** @type {import("next").NextConfig} */
const nextConfig = {
  turbopack: {
    root: appRoot,
  },
  async rewrites() {
    const backendOrigin = getBackendOrigin();
    if (!backendOrigin) {
      return [];
    }

    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

function getBackendOrigin() {
  const rawOrigin = process.env.BACKEND_ORIGIN?.trim();
  if (!rawOrigin) {
    if (process.env.VERCEL) {
      throw new Error(
        "BACKEND_ORIGIN is required for Vercel deployments so /api/* rewrites can reach the backend.",
      );
    }
    return null;
  }

  const withoutTrailingSlash = rawOrigin.replace(/\/+$/, "");
  let url;
  try {
    url = new URL(withoutTrailingSlash);
  } catch {
    throw new Error("BACKEND_ORIGIN must be an absolute http(s) URL.");
  }

  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error("BACKEND_ORIGIN must use http or https.");
  }
  if (url.pathname !== "/" && url.pathname !== "") {
    throw new Error("BACKEND_ORIGIN must be an origin without a path.");
  }

  return url.origin;
}

export default nextConfig;
