const https = require("https");

module.exports = (req, res) => {
  const backend = process.env.BACKEND_URL;
  const apiKey = process.env.DOCUSENSE_API_KEY;

  if (!backend || !apiKey) {
    return res.status(500).json({
      detail: "Proxy environment variables are missing"
    });
  }

  const incoming = new URL(req.url, "https://vercel.local");
  const base = new URL(backend);

  const apiPath = incoming.pathname.replace(/^\/api/, "") || "/";
  const upstreamPath = `${base.pathname.replace(/\/$/, "")}${apiPath}${incoming.search}`;

  const headers = { ...req.headers };
  delete headers.host;
  delete headers.connection;
  delete headers["transfer-encoding"];

  headers["x-api-key"] = apiKey;

  const proxy = https.request(
    {
      hostname: base.hostname,
      port: base.port || 443,
      path: upstreamPath,
      method: req.method,
      headers
    },
    (response) => {
      res.statusCode = response.statusCode;

      Object.entries(response.headers).forEach(([key, value]) => {
        if (!["connection", "transfer-encoding"].includes(key.toLowerCase()) && value !== undefined) {
          res.setHeader(key, value);
        }
      });

      response.pipe(res);
    }
  );

  proxy.on("error", (error) => {
    console.error("Backend proxy error:", error.message);
    if (!res.headersSent) {
      res.statusCode = 502;
      res.end("Backend connection failed");
    }
  });

  req.pipe(proxy);
};