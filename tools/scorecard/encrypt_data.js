// Encrypts the website's data for public hosting: gzip, then AES-256-GCM with a key derived from a passphrase
// (PBKDF2-SHA256). Uses the same Web Crypto calls the browser uses to decrypt it in site/app.js.
//
//     SCORECARD_PASSPHRASE=... node tools/scorecard/encrypt_data.js <data.json> <data.enc.json>
//
// Called by build_site.py --publish; the passphrase comes through the environment so it never appears in a
// command line. The result is decrypted again before it is written, so a broken file is never published.
"use strict";
const { webcrypto } = require("crypto");
const fs = require("fs");
const zlib = require("zlib");

const ITERATIONS = 600000;            // OWASP's figure for PBKDF2-SHA256; ~0.5 s once per browser session
const subtle = webcrypto.subtle;
const b64 = buf => Buffer.from(buf).toString("base64");

async function key(pass, salt, usage) {
  const base = await subtle.importKey("raw", new TextEncoder().encode(pass), "PBKDF2", false, ["deriveKey"]);
  return subtle.deriveKey({ name: "PBKDF2", salt, iterations: ITERATIONS, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, [usage]);
}

(async () => {
  const [src, dst] = process.argv.slice(2);
  const pass = process.env.SCORECARD_PASSPHRASE;
  if (!src || !dst || !pass) { console.error("usage: SCORECARD_PASSPHRASE=... node encrypt_data.js <data.json> <data.enc.json>"); process.exit(2); }
  const plain = fs.readFileSync(src);
  JSON.parse(plain.toString("utf8"));                       // refuse to encrypt something that is not the site data
  const packed = zlib.gzipSync(plain, { level: 9 });
  const salt = webcrypto.getRandomValues(new Uint8Array(16)), iv = webcrypto.getRandomValues(new Uint8Array(12));
  const ct = await subtle.encrypt({ name: "AES-GCM", iv }, await key(pass, salt, "encrypt"), packed);
  const back = zlib.gunzipSync(Buffer.from(await subtle.decrypt({ name: "AES-GCM", iv }, await key(pass, salt, "decrypt"), ct)));
  if (!back.equals(plain)) throw new Error("round trip failed");
  const env = { format: "p12s-scorecard", version: 1, kdf: "PBKDF2-SHA256", iterations: ITERATIONS, cipher: "AES-256-GCM",
                compressed: "gzip", salt: b64(salt), iv: b64(iv), data: b64(ct) };
  fs.writeFileSync(dst, JSON.stringify(env));
  console.log(`encrypted ${plain.length} bytes -> ${fs.statSync(dst).size} bytes (round trip checked)`);
})().catch(e => { console.error(e.message || e); process.exit(1); });
