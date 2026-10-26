import nextEnv from "@next/env";
import { spawn } from "node:child_process";
import { cpSync, existsSync } from "node:fs";
import path from "node:path";

nextEnv.loadEnvConfig(path.resolve(process.cwd(), ".."));
const mode = process.argv[2] || "dev";
let args;
let serverEnvironment = process.env;
if (mode === "start") {
  const standalone = path.resolve(".next/standalone");
  const server = path.join(standalone, "server.js");
  if (!existsSync(server)) {
    process.stderr.write("Bitte zuerst npm run build ausführen.\n");
    process.exit(1);
  }
  cpSync(path.resolve(".next/static"), path.join(standalone, ".next/static"), { recursive: true });
  if (existsSync("public")) cpSync(path.resolve("public"), path.join(standalone, "public"), { recursive: true });
  args = [server];
  serverEnvironment = { ...process.env, HOSTNAME: "127.0.0.1", PORT: process.env.FRONTEND_PORT || "3010" };
} else {
  args = ["node_modules/next/dist/bin/next", mode, ...(mode === "build" ? [] : ["--hostname", "127.0.0.1", "--port", process.env.FRONTEND_PORT || "3010"])];
}
const child = spawn(process.execPath, args, { stdio: "inherit", env: serverEnvironment });
for (const signal of ["SIGINT", "SIGTERM"]) process.on(signal, () => child.kill(signal));
child.on("exit", (code) => process.exit(code ?? 1));
