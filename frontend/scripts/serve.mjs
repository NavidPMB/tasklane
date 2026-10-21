import nextEnv from "@next/env";
import { spawn } from "node:child_process";
import path from "node:path";

nextEnv.loadEnvConfig(path.resolve(process.cwd(), ".."));
const mode = process.argv[2] || "dev";
const networkArguments = mode === "build" ? [] : [
  "--hostname", "127.0.0.1", "--port", process.env.FRONTEND_PORT || "3002",
];
const child = spawn(
  process.execPath,
  [
    "node_modules/next/dist/bin/next",
    mode,
    ...networkArguments,
  ],
  {
    stdio: "inherit",
    env: process.env,
  },
);
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 1));
