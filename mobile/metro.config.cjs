const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);
// The native screen and retained browser preview share the tested API client.
config.resolver.sourceExts = [...new Set([...config.resolver.sourceExts, "mjs"])];

module.exports = config;
