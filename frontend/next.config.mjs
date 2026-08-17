/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // three.js and react-force-graph ship ESM that Next transpiles per-package.
  transpilePackages: ["three", "react-force-graph-3d"],
};

export default nextConfig;
