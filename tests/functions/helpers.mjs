// 테스트 공용: 가짜 KV, 가짜 Access 토큰
export function kv() {
  const m = new Map();
  return {
    m,
    put: async (k, v) => m.set(k, typeof v === "string" ? v : new Uint8Array(v)),
    get: async (k) => (m.has(k) ? m.get(k) : null),
    delete: async (k) => m.delete(k),
    list: async () => ({ keys: [...m.keys()].sort().map((name) => ({ name })), list_complete: true }),
  };
}

const b64url = (buf) => Buffer.from(buf).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const RSA = { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" };

export async function accessKeys() {
  const { privateKey, publicKey } = await crypto.subtle.generateKey(RSA, true, ["sign", "verify"]);
  const jwk = { ...(await crypto.subtle.exportKey("jwk", publicKey)), kid: "k1" };
  return { privateKey, certs: { keys: [jwk] } };
}

export async function otherKey() {
  return (await crypto.subtle.generateKey(RSA, true, ["sign"])).privateKey;
}

export async function jwt(payload, key) {
  const h = b64url(JSON.stringify({ alg: "RS256", kid: "k1" }));
  const p = b64url(JSON.stringify(payload));
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${h}.${p}`));
  return `${h}.${p}.${b64url(sig)}`;
}

export const soon = () => Math.floor(Date.now() / 1000) + 600;
