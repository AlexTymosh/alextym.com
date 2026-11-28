import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores([
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
    // Generated artifacts are not application source code.
    "**/playwright-report/**",
    "**/test-results/**",
    "**/dist/**",
    "**/.generated/**",
  ]),
]);

export default eslintConfig;
