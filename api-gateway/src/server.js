const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const port = process.env.PORT || 8000;

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'OK' });
});

// Proxy configuration
app.use(
  '/chat',
  createProxyMiddleware({
    target: process.env.CHAT_SERVICE_URL,
    changeOrigin: true,
    pathRewrite: { '^/chat': '' }
  })
);

app.use(
  '/conversations',
  createProxyMiddleware({
    target: process.env.CONVERSATION_SERVICE_URL,
    changeOrigin: true,
    pathRewrite: { '^/conversations': '' }
  })
);

app.listen(port, () => {
  console.log(`API Gateway running on port ${port}`);
}); 