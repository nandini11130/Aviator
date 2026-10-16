/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export so the whole frontend can be hosted for free on Firebase
  // Hosting; the backend (FastAPI + ADK agents) lives separately on Cloud Run.
  output: "export",
  images: { unoptimized: true },
};

module.exports = nextConfig;
