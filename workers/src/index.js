/**
 * BlackRoad Dotfiles Worker
 * Handles long-running sync tasks, manifest validation, and scheduled health checks.
 *
 * Copyright (c) 2024-2026 BlackRoad OS, Inc. All Rights Reserved.
 * Proprietary and Confidential.
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    try {
      switch (url.pathname) {
        case "/health":
          return json({ status: "ok", timestamp: new Date().toISOString() });

        case "/api/validate-manifest":
          if (request.method !== "POST") return json({ error: "POST required" }, 405);
          return handleValidateManifest(request, env);

        case "/api/sync-status":
          return handleSyncStatus(env);

        case "/api/trigger-sync":
          if (request.method !== "POST") return json({ error: "POST required" }, 405);
          ctx.waitUntil(handleLongRunningSync(env));
          return json({ status: "accepted", message: "Sync started in background" });

        default:
          return json({ error: "Not found" }, 404);
      }
    } catch (err) {
      return json({ error: "Internal server error" }, 500);
    }
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(handleScheduledHealthCheck(env));
  },
};

async function handleValidateManifest(request, env) {
  const body = await request.json();
  if (!Array.isArray(body)) {
    return json({ valid: false, error: "Manifest must be an array" }, 400);
  }
  const required = ["name", "source_path", "target_path"];
  const errors = [];
  body.forEach((entry, i) => {
    required.forEach((field) => {
      if (!entry[field]) errors.push(`Entry ${i}: missing '${field}'`);
    });
    const validCategories = ["shell", "editor", "git", "tmux", "tool"];
    if (entry.category && !validCategories.includes(entry.category)) {
      errors.push(`Entry ${i}: invalid category '${entry.category}'`);
    }
  });
  return json({ valid: errors.length === 0, errors, entries: body.length });
}

async function handleSyncStatus(env) {
  const lastSync = await env.DOTFILES_KV?.get("last_sync");
  const syncCount = await env.DOTFILES_KV?.get("sync_count");
  return json({
    last_sync: lastSync || null,
    sync_count: parseInt(syncCount || "0"),
    status: "idle",
  });
}

async function handleLongRunningSync(env) {
  const timestamp = new Date().toISOString();
  const count = parseInt((await env.DOTFILES_KV?.get("sync_count")) || "0");
  await env.DOTFILES_KV?.put("last_sync", timestamp);
  await env.DOTFILES_KV?.put("sync_count", String(count + 1));
}

async function handleScheduledHealthCheck(env) {
  const timestamp = new Date().toISOString();
  await env.DOTFILES_KV?.put("last_health_check", timestamp);
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders() },
  });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
}
