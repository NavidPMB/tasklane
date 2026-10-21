import nextEnv from "@next/env";
import path from "node:path";
import { fileURLToPath } from "node:url";

nextEnv.loadEnvConfig(
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."),
);
const backend = (process.env.BACKEND_URL || "http://127.0.0.1:8002").replace(
  /\/$/,
  "",
);

export default {
  poweredByHeader: false,
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return ["api", "accounts", "django-admin", "static"].map((prefix) => ({
      source: `/${prefix}/:path*`,
      destination: `${backend}/${prefix}/:path*${prefix === "static" ? "" : "/"}`,
    }));
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
        ],
      },
    ];
  },
};
