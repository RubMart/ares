/** @type {import('next').NextConfig} */
const nextConfig = {
  // Next 16 blocks cross-origin HMR (localhost vs 127.0.0.1) unless allow-listed.
  allowedDevOrigins: ['127.0.0.1', 'localhost'],
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
}

export default nextConfig
