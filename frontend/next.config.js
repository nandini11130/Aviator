/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export so the whole frontend can be hosted for free on Firebase
  // Hosting; the backend (FastAPI + ADK agents) lives separately on Cloud Run.
  output: "export",
  // Keep `next dev` artifacts separate from production builds so running a
  // build cannot corrupt a development server's generated chunks.
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
  images: { unoptimized: true },
};

module.exports = nextConfig;
